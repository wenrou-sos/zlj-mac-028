"""车辆与人员资源状态管理：送修/复归、请假/复岗、占用冲突检查。"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Role
from .models import (PersonnelStatusLog, Task, TaskAssignee, TaskStatus,
                     Vehicle, VehicleStatusLog)
from .permissions import require_dispatcher


class ResourceService:
    # ---------- 占用检查 ----------
    @staticmethod
    def vehicle_busy_task(vehicle, on_date=None):
        """返回占用该车辆的未完成任务（可选限定日期）。"""
        qs = (Task.objects.filter(vehicle=vehicle)
              .exclude(status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED]))
        if on_date:
            qs = qs.filter(planned_date=on_date)
        return qs.select_related('vehicle').order_by('-planned_date').first()

    @staticmethod
    def user_busy_tasks(user):
        """返回该人员被排班的未完成任务。"""
        return list(
            Task.objects.filter(taskassignee__user=user)
            .exclude(status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED])
            .select_related('vehicle')
            .order_by('-planned_date'))

    @staticmethod
    def vehicle_unavailable_reason(vehicle, on_date=None):
        """排班选车时返回不可用原因；可用返回 None。"""
        if vehicle.status == Vehicle.Status.MAINTENANCE:
            return f'车辆 {vehicle.plate} 维修中，暂不可派'
        busy = ResourceService.vehicle_busy_task(vehicle, on_date)
        if busy:
            return (f'车辆 {vehicle.plate} 当天已执行任务 {busy.task_no}'
                    f'（{busy.get_status_display()}）')
        return None

    @staticmethod
    def user_unavailable_reason(user, on_date=None, role_on_task=None):
        """排班选人时返回不可用原因；可用返回 None。"""
        if not user.is_active:
            return f'{user.name} 账号已停用'
        if not user.active_duty:
            kind = user.duty_display
            return f'{user.name} 今日{kind}，不能排班'
        if role_on_task == 'driver' and user.role != Role.DRIVER:
            return f'{user.name} 不是驾驶员'
        if role_on_task == 'car_captain' and user.role != Role.GUARD:
            return f'{user.name} 非押运岗，不能担任车长'
        if role_on_task == 'guard' and user.role != Role.GUARD:
            return f'{user.name} 非押运岗，不能担任押运员'
        busy = ResourceService.user_busy_tasks(user)
        if on_date:
            busy = [t for t in busy if t.planned_date == on_date]
        if busy:
            t = busy[0]
            return f'{user.name} 已被任务 {t.task_no} 占用（{t.get_status_display()}）'
        return None

    # ---------- 车辆 ----------
    @staticmethod
    @transaction.atomic
    def send_vehicle_repair(vehicle, reason, operator):
        require_dispatcher(operator, '车辆送修登记')
        if vehicle.status == Vehicle.Status.MAINTENANCE:
            raise ValidationError('车辆已处于维修状态')
        busy = ResourceService.vehicle_busy_task(vehicle)
        if busy:
            raise ValidationError(
                f'车辆正执行任务 {busy.task_no}（{busy.get_status_display()}），'
                f'任务办结或取消后才能登记送修')
        old = vehicle.status
        vehicle.status = Vehicle.Status.MAINTENANCE
        vehicle.save(update_fields=['status'])
        log = VehicleStatusLog.objects.create(
            vehicle=vehicle, from_status=old,
            to_status=Vehicle.Status.MAINTENANCE,
            reason=reason or '登记送修', operator=operator)
        return log

    @staticmethod
    @transaction.atomic
    def return_vehicle_service(vehicle, operator):
        require_dispatcher(operator, '车辆复归待命')
        if vehicle.status != Vehicle.Status.MAINTENANCE:
            raise ValidationError('仅维修中的车辆可以复归待命')
        old = vehicle.status
        vehicle.status = Vehicle.Status.IDLE
        vehicle.save(update_fields=['status'])
        return VehicleStatusLog.objects.create(
            vehicle=vehicle, from_status=old, to_status=Vehicle.Status.IDLE,
            reason='维修完成，复归待命', operator=operator)

    @staticmethod
    def log_vehicle_dispatch(vehicle, task, operator):
        """派车/出发等系统占用留痕（不阻断）。"""
        return VehicleStatusLog.objects.create(
            vehicle=vehicle, from_status=Vehicle.Status.IDLE,
            to_status=Vehicle.Status.ON_DUTY,
            reason=f'执行任务 {task.task_no}', task=task, operator=operator)

    # ---------- 人员 ----------
    @staticmethod
    @transaction.atomic
    def staff_leave(user, leave_type, reason, operator):
        require_dispatcher(operator, '人员请假登记')
        if not user.active_duty:
            raise ValidationError(f'{user.name} 已处于{user.duty_display}状态')
        busy = ResourceService.user_busy_tasks(user)
        if busy:
            t = busy[0]
            raise ValidationError(
                f'{user.name} 被未完成任务 {t.task_no}（{t.get_status_display()}）'
                f'占用，请先调整车组或办结任务')
        user.active_duty = False
        user.leave_type = leave_type or 'rest'
        user.save(update_fields=['active_duty', 'leave_type'])
        return PersonnelStatusLog.objects.create(
            user=user, active_duty=False,
            leave_type=user.leave_type,
            reason=reason or user.get_leave_type_display(), operator=operator)

    @staticmethod
    @transaction.atomic
    def staff_return(user, operator):
        require_dispatcher(operator, '人员复岗登记')
        if user.active_duty:
            raise ValidationError(f'{user.name} 已在岗，无需复岗')
        user.active_duty = True
        user.leave_type = ''
        user.save(update_fields=['active_duty', 'leave_type'])
        return PersonnelStatusLog.objects.create(
            user=user, active_duty=True, leave_type='',
            reason='复岗', operator=operator)

    # ---------- 交接在岗校验 ----------
    @staticmethod
    def require_on_duty(user, where):
        if user is None:
            raise ValidationError('交接必须登记交出人和接收人（双人核对）')
        if not user.is_active:
            raise ValidationError(f'{where}人员 {user.name} 账号已停用')
        if not user.active_duty:
            raise ValidationError(f'{where}人员 {user.name} 今日{user.duty_display}，'
                                  f'不能办理交接')
        return True
