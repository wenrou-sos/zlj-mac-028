"""押运任务流转服务：状态机、交接核对、异常联动。"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User

from .models import (BoxTaskStatus, CashBox, Handover, HandoverPhase, Incident,
                     PersonnelStatusLog, StopStatus, Task, TaskAssignee, TaskBox,
                     TaskLog, TaskRole, TaskStatus, TaskStop, Vehicle,
                     VehicleStatusLog)
from .models_base import BranchType
from .resource_service import ResourceService


class TaskService:
    # ---------- 创建 ----------
    @staticmethod
    @transaction.atomic
    def create_task(validated, creator):
        route = validated['route_id']
        if isinstance(route, int):
            from .models import Route
            route = Route.objects.get(id=route)
        vehicle = validated['vehicle_id']
        if isinstance(vehicle, int):
            vehicle = Vehicle.objects.get(id=vehicle)

        vehicle_reason = ResourceService.vehicle_unavailable_reason(
            vehicle, validated['planned_date'])
        if vehicle_reason:
            raise ValidationError(vehicle_reason)

        task = Task.objects.create(
            direction=validated['direction'],
            route=route, depot=route.depot, vehicle=vehicle,
            planned_date=validated['planned_date'],
            planned_depart=validated.get('planned_depart'),
            planned_return=validated.get('planned_return'),
            name=validated.get('name') or f'{route.name}押运任务',
            notes=validated.get('notes', ''),
            creator=creator,
            status=TaskStatus.PLANNED,
        )

        # 停靠点（含随机交接验证码）
        stops = []
        for i, rs in enumerate(route.stops.select_related('branch'), start=1):
            planned_dt = None
            if rs.planned_arrival:
                planned_dt = timezone.make_aware(
                    timezone.datetime.combine(task.planned_date,
                                              rs.planned_arrival))
            stop = TaskStop.objects.create(
                task=task, sequence=i, branch=rs.branch,
                planned_arrival=planned_dt,
                status=StopStatus.EN_ROUTE if i == 1 else StopStatus.PENDING,
                verify_code=TaskStop.generate_code(),
            )
            stops.append(stop)

        # 人员（在岗、岗位匹配、同日任务占用逐项校验，给出明确冲突原因）
        for a in validated['assignees']:
            user = User.objects.filter(id=a['user_id']).first()
            if user is None:
                raise ValidationError('所选人员不存在')
            reason = ResourceService.user_unavailable_reason(
                user, validated['planned_date'], a['role_on_task'])
            if reason:
                raise ValidationError(reason)
            TaskAssignee.objects.create(task=task, user=user,
                                        role_on_task=a['role_on_task'])

        # 款箱
        direction = validated['direction']
        # 下解只能取在库空闲箱；上收只能取已送达网点、等待回收的箱
        allow_box_status = (CashBox.Status.IDLE if direction == Task.Direction.OUTBOUND
                            else CashBox.Status.DELIVERED)
        require_text = '在库空闲' if direction == Task.Direction.OUTBOUND else '已送达网点待回收'
        stop_by_seq = {s.sequence: s for s in stops}
        for b in validated['boxes']:
            seq = b['target_stop_sequence']
            if seq not in stop_by_seq:
                raise ValidationError(f'停靠点顺序 {seq} 不存在')
            stop = stop_by_seq[seq]
            box = CashBox.objects.select_for_update().get(id=b['box_id'])
            if box.status != allow_box_status:
                raise ValidationError(
                    f'款箱 {box.box_no} 当前为「{box.get_status_display()}」，'
                    f'{"下解" if direction == Task.Direction.OUTBOUND else "上收"}'
                    f'任务要求款箱{require_text}')
            occupied = (TaskBox.objects.filter(box=box)
                        .exclude(task__status__in=[TaskStatus.COMPLETED,
                                                   TaskStatus.CANCELLED])
                        .exists())
            if occupied:
                raise ValidationError(f'款箱 {box.box_no} 已被其他未完成任务占用')
            if box.owner_branch_id != stop.branch_id:
                raise ValidationError(
                    f'款箱 {box.box_no} 归属{box.owner_branch.name}，'
                    f'不能在 {stop.branch.name} 办理交接')
            TaskBox.objects.create(
                task=task, box=box, target_stop=stop,
                status=BoxTaskStatus.PENDING_OUT,
            )

        TaskService._log(task, 'task_created',
                         f'任务已创建并派车：{task.name}，车辆 {vehicle.plate}，'
                         f'{len(stops)} 个停靠点', creator)
        return task

    # ---------- 出发 ----------
    @staticmethod
    @transaction.atomic
    def depart(task, actor):
        if task.status != TaskStatus.PLANNED:
            raise ValidationError('只有已派车状态的任务才能出发')
        if task.direction == Task.Direction.OUTBOUND:
            missing = task.taskbox_set.filter(
                status=BoxTaskStatus.PENDING_OUT).count()
            if missing:
                raise ValidationError(
                    f'还有 {missing} 个款箱未完成金库出库核对，不能出发')
        task.status = TaskStatus.IN_TRANSIT
        task.actual_depart = timezone.now()
        task.save(update_fields=['status', 'actual_depart', 'updated_at'])
        task.vehicle.status = Vehicle.Status.ON_DUTY
        task.vehicle.save(update_fields=['status'])
        ResourceService.log_vehicle_dispatch(task.vehicle, task, actor)
        TaskService._log(task, 'depart',
                         f'车辆 {task.vehicle.plate} 从{task.depot.name}出发', actor)
        return task

    # ---------- 到达停靠点 ----------
    @staticmethod
    @transaction.atomic
    def arrive_stop(task, stop_id, actor):
        stop = task.stops.filter(id=stop_id).first()
        if not stop:
            raise ValidationError('停靠点不存在')
        if stop.status not in (StopStatus.EN_ROUTE, StopStatus.PENDING):
            raise ValidationError('该停靠点已到达或已完成')
        if task.status != TaskStatus.IN_TRANSIT:
            raise ValidationError('任务不在押运中')
        stop.status = StopStatus.ARRIVED
        stop.actual_arrival = timezone.now()
        stop.save(update_fields=['status', 'actual_arrival'])
        TaskService._log(task, 'arrive',
                         f'到达第{stop.sequence}站 {stop.branch.name}，'
                         f'交接验证码 {stop.verify_code}', actor, stop=stop)
        return stop

    # ---------- 款箱交接（核心核对） ----------
    @staticmethod
    @transaction.atomic
    def handover(task, data, actor):
        tb = task.taskbox_set.select_related('box', 'target_stop').filter(
            id=data['task_box_id']).first()
        if not tb:
            raise ValidationError('任务款箱不存在')
        phase = data['phase']
        stop = tb.target_stop
        now = timezone.now()

        if not data.get('from_user_id') or not data.get('to_user_id'):
            raise ValidationError('交接必须登记交出人和接收人（双人核对）')
        from_person = User.objects.filter(id=data['from_user_id']).first()
        to_person = User.objects.filter(id=data['to_user_id']).first()
        ResourceService.require_on_duty(from_person, '交出方')
        ResourceService.require_on_duty(to_person, '接收方')

        # 阶段与前置校验
        if phase == HandoverPhase.VAULT_OUT:
            if task.direction != Task.Direction.OUTBOUND:
                raise ValidationError('上收任务不做出库交接')
            if tb.status != BoxTaskStatus.PENDING_OUT:
                raise ValidationError('该款箱已出库')
            seal_in = (data.get('seal_no_in') or '').strip()
            if not seal_in:
                raise ValidationError('请录入金库封签号')
            tb.seal_no = seal_in
            tb.status = BoxTaskStatus.IN_TRANSIT
            tb.save()
            tb.box.status = CashBox.Status.IN_TRANSIT
            tb.box.save(update_fields=['status'])
            result = Handover.Result.CONFIRMED
            code_ok = None
            message = f'款箱 {tb.box.box_no} 金库出库核对一致，封签 {seal_in}'

        elif phase == HandoverPhase.BRANCH_RECV:
            TaskService._check_arrived(stop)
            if tb.status != BoxTaskStatus.IN_TRANSIT:
                raise ValidationError('款箱状态不允许网点接收')
            code_ok, seal_ok, result = TaskService._verify(task, tb, stop, data)
            if result == Handover.Result.CONFIRMED:
                tb.status = BoxTaskStatus.DELIVERED
                tb.box.status = CashBox.Status.DELIVERED
                message = f'款箱 {tb.box.box_no} 送达 {stop.branch.name}，核对一致'
            else:
                message = f'款箱 {tb.box.box_no} 接收核对异常：{result.label}'
                TaskService._flag_exception(task, tb, stop, result, actor, data)
            tb.save()
            tb.box.save(update_fields=['status'])

        elif phase == HandoverPhase.BRANCH_PICKUP:
            TaskService._check_arrived(stop)
            if task.direction != Task.Direction.INBOUND:
                raise ValidationError('下解任务不做网点移交')
            if tb.status != BoxTaskStatus.PENDING_OUT:
                raise ValidationError('该款箱已装车')
            code_ok, seal_ok, result = TaskService._verify(task, tb, stop, data,
                                                           require_seal=False)
            if result == Handover.Result.CONFIRMED:
                seal_in = (data.get('seal_no_in') or '').strip()
                if not seal_in:
                    raise ValidationError('请录入网点封签号')
                tb.seal_no = seal_in
                tb.status = BoxTaskStatus.IN_TRANSIT
                tb.box.status = CashBox.Status.IN_TRANSIT
                message = f'款箱 {tb.box.box_no} 从 {stop.branch.name} 上收装车，核对一致'
            else:
                message = f'款箱 {tb.box.box_no} 移交核对异常：{result.label}'
                TaskService._flag_exception(task, tb, stop, result, actor, data)
            tb.save()
            tb.box.save(update_fields=['status'])

        elif phase == HandoverPhase.VAULT_RETURN:
            if tb.status != BoxTaskStatus.IN_TRANSIT:
                raise ValidationError('款箱不在返程在途状态')
            seal_in = (data.get('seal_no_in') or '').strip()
            result = Handover.Result.CONFIRMED
            code_ok = None
            if seal_in and tb.seal_no and seal_in != tb.seal_no:
                result = Handover.Result.SEAL_MISMATCH
                TaskService._flag_exception(task, tb, stop, result, actor, data)
                message = f'款箱 {tb.box.box_no} 回库封签不符'
            else:
                tb.status = BoxTaskStatus.RETURNED
                tb.box.status = CashBox.Status.IDLE
                tb.box.save(update_fields=['status'])
                message = f'款箱 {tb.box.box_no} 回库核对一致，已入库'
            tb.save()
        else:
            raise ValidationError('未知交接阶段')

        h = Handover.objects.create(
            task_box=tb, phase=phase, stop=stop,
            result=result,
            seal_no_out=tb.seal_no or '',
            seal_no_in=(data.get('seal_no_in') or '').strip(),
            seal_intact=data.get('seal_intact', True),
            code_verified=code_ok,
            from_person_id=data.get('from_user_id'),
            to_person_id=data.get('to_user_id'),
            operator=actor, remark=data.get('remark', ''),
        )

        if result == Handover.Result.CONFIRMED:
            TaskService._log(task, 'handover', message, actor, stop=stop)
            TaskService._maybe_finish_stop(task, stop, actor)
            TaskService._maybe_complete(task, actor)
        else:
            TaskService._log(task, 'handover_fail', message, actor, stop=stop)
        return h

    @staticmethod
    def _check_arrived(stop):
        if stop.status not in (StopStatus.ARRIVED, StopStatus.DONE):
            raise ValidationError(f'尚未到达 {stop.branch.name}，不能交接')

    @staticmethod
    def _verify(task, tb, stop, data, require_seal=True):
        """验证码 + 封签双人核对。返回 (code_ok, seal_ok, result)。"""
        code = (data.get('code') or '').strip()
        code_ok = code == stop.verify_code
        seal_given = (data.get('seal_no_in') or '').strip()
        if require_seal and tb.seal_no:
            seal_ok = bool(seal_given) and seal_given == tb.seal_no
        else:
            # 封签首次登记（上收移交）仅要求非空
            seal_ok = bool(seal_given)
        if not code_ok:
            return code_ok, seal_ok, Handover.Result.CODE_MISMATCH
        if require_seal and tb.seal_no and not seal_ok:
            return code_ok, seal_ok, Handover.Result.SEAL_MISMATCH
        if data.get('seal_intact', True) is False:
            return code_ok, seal_ok, Handover.Result.SEAL_MISMATCH
        return True, True, Handover.Result.CONFIRMED

    @staticmethod
    def _flag_exception(task, tb, stop, result, actor, data):
        tb.exception_flag = True
        category = {'seal_mismatch': Incident.Category.SEAL,
                    'code_mismatch': Incident.Category.SECURITY,
                    'box_missing': Incident.Category.BOX_MISSING}[result.value]
        Incident.objects.create(
            task=task, stop=stop, task_box=tb, category=category,
            severity=Incident.Severity.HIGH,
            description=f'{result.label}：款箱 {tb.box.box_no}，'
                        f'阶段 {data["phase"]}。{data.get("remark", "")}',
            reported_by=actor,
        )
        task.status = TaskStatus.ABNORMAL
        task.save(update_fields=['status', 'updated_at'])

    @staticmethod
    def _maybe_finish_stop(task, stop, actor):
        expect = BoxTaskStatus.DELIVERED if task.direction == Task.Direction.OUTBOUND \
            else BoxTaskStatus.IN_TRANSIT
        # 上收时装车即可；下解时送达
        qs = stop.task_boxes.all()
        if not qs:
            return
        done = all(tb.status in (expect, BoxTaskStatus.RETURNED) for tb in qs) \
            if task.direction == Task.Direction.OUTBOUND else \
            all(tb.status in (expect, BoxTaskStatus.RETURNED, BoxTaskStatus.DELIVERED)
                for tb in qs)
        if done and stop.status != StopStatus.DONE:
            stop.status = StopStatus.DONE
            stop.actual_departure = timezone.now()
            stop.save(update_fields=['status', 'actual_departure'])
            TaskService._log(task, 'stop_done',
                             f'{stop.branch.name} 交接完成，车辆驶离', actor, stop=stop)
            nxt = task.stops.filter(sequence=stop.sequence + 1).first()
            if nxt and nxt.status == StopStatus.PENDING:
                nxt.status = StopStatus.EN_ROUTE
                nxt.save(update_fields=['status'])
                TaskService._log(task, 'en_route',
                                 f'驶向下一站 {nxt.branch.name}', actor)

    @staticmethod
    def _maybe_complete(task, actor):
        terminal = BoxTaskStatus.DELIVERED if task.direction == Task.Direction.OUTBOUND \
            else BoxTaskStatus.RETURNED
        all_done = not task.taskbox_set.exclude(status=terminal).exists()
        stops_done = not task.stops.exclude(status=StopStatus.DONE).exists()
        open_inc = task.incidents.exclude(status=Incident.Status.RESOLVED).exists()
        if all_done and stops_done and not open_inc and task.status != TaskStatus.COMPLETED:
            task.status = TaskStatus.COMPLETED
            task.actual_return = timezone.now()
            task.save(update_fields=['status', 'actual_return', 'updated_at'])
            task.vehicle.status = Vehicle.Status.IDLE
            task.vehicle.save(update_fields=['status'])
            VehicleStatusLog.objects.create(
                vehicle=task.vehicle, from_status=Vehicle.Status.ON_DUTY,
                to_status=Vehicle.Status.IDLE,
                reason=f'任务 {task.task_no} 完成，车辆归队',
                task=task, operator=actor)
            TaskService._log(task, 'completed',
                             '全部交接完成，任务结束，车辆归队', actor)

    # ---------- 手动完成停靠点 / 任务 ----------
    @staticmethod
    @transaction.atomic
    def finish_stop(task, stop_id, actor):
        stop = task.stops.filter(id=stop_id).first()
        if not stop:
            raise ValidationError('停靠点不存在')
        if stop.status == StopStatus.DONE:
            raise ValidationError('停靠点已完成')
        stop.status = StopStatus.DONE
        stop.actual_departure = timezone.now()
        stop.save(update_fields=['status', 'actual_departure'])
        TaskService._log(task, 'stop_done', f'{stop.branch.name} 交接完成（手动办结）',
                         actor, stop=stop)
        nxt = task.stops.filter(sequence=stop.sequence + 1).first()
        if nxt and nxt.status == StopStatus.PENDING:
            nxt.status = StopStatus.EN_ROUTE
            nxt.save(update_fields=['status'])
        return stop

    @staticmethod
    @transaction.atomic
    def complete(task, actor):
        terminal = BoxTaskStatus.DELIVERED if task.direction == Task.Direction.OUTBOUND \
            else BoxTaskStatus.RETURNED
        unfinished = task.taskbox_set.exclude(status=terminal).count()
        if unfinished:
            raise ValidationError(f'还有 {unfinished} 个款箱未完成最终交接')
        open_inc = task.incidents.exclude(status=Incident.Status.RESOLVED).count()
        if open_inc:
            raise ValidationError(f'还有 {open_inc} 起异常未处置')
        task.status = TaskStatus.COMPLETED
        task.actual_return = timezone.now()
        task.save(update_fields=['status', 'actual_return', 'updated_at'])
        task.vehicle.status = Vehicle.Status.IDLE
        task.vehicle.save(update_fields=['status'])
        VehicleStatusLog.objects.create(
            vehicle=task.vehicle, from_status=Vehicle.Status.ON_DUTY,
            to_status=Vehicle.Status.IDLE,
            reason=f'任务 {task.task_no} 完成，车辆归队',
            task=task, operator=actor)
        TaskService._log(task, 'completed', '任务完成，车辆归队', actor)
        return task

    @staticmethod
    @transaction.atomic
    def cancel(task, actor, reason=''):
        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            raise ValidationError('终态任务不可取消')
        task.status = TaskStatus.CANCELLED
        task.notes = (task.notes + f'｜取消原因：{reason}').strip()
        task.save(update_fields=['status', 'notes', 'updated_at'])
        old_vehicle_status = task.vehicle.status
        task.vehicle.status = Vehicle.Status.IDLE
        task.vehicle.save(update_fields=['status'])
        if old_vehicle_status == Vehicle.Status.ON_DUTY:
            VehicleStatusLog.objects.create(
                vehicle=task.vehicle, from_status=old_vehicle_status,
                to_status=Vehicle.Status.IDLE,
                reason=f'任务 {task.task_no} 取消，车辆归队',
                task=task, operator=actor)
        restore_status = (CashBox.Status.IDLE if task.direction == Task.Direction.OUTBOUND
                          else CashBox.Status.DELIVERED)
        box_ids = list(task.taskbox_set.values_list('box_id', flat=True))
        task.taskbox_set.update(status=BoxTaskStatus.PENDING_OUT, exception_flag=False)
        CashBox.objects.filter(id__in=box_ids).update(status=restore_status)
        TaskService._log(task, 'cancelled', f'任务取消：{reason}', actor)
        return task

    # ---------- 异常 ----------
    @staticmethod
    @transaction.atomic
    def report_incident(task, data, actor):
        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            raise ValidationError('已办结或已取消的任务不能上报异常')
        inc = Incident.objects.create(
            task=task, stop_id=data.get('stop'), task_box_id=data.get('task_box'),
            category=data['category'], severity=data['severity'],
            description=data['description'], reported_by=actor,
            status=Incident.Status.OPEN,
        )
        if data.get('task_box'):
            task.taskbox_set.filter(id=data['task_box']).update(exception_flag=True)
        task.status = TaskStatus.ABNORMAL
        task.save(update_fields=['status', 'updated_at'])
        TaskService._log(task, 'incident',
                         f'上报异常 {inc.get_category_display()}：'
                         f'{inc.description[:50]}', actor, stop_id=data.get('stop'))
        return inc

    @staticmethod
    @transaction.atomic
    def resolve_incident(task, incident_id, actor, resolution):
        inc = task.incidents.filter(id=incident_id).first()
        if not inc:
            raise ValidationError('异常事件不存在')
        inc.status = Incident.Status.RESOLVED
        inc.resolution = resolution
        inc.resolved_by = actor
        inc.resolved_at = timezone.now()
        inc.save(update_fields=['status', 'resolution', 'resolved_by', 'resolved_at'])
        TaskService._log(task, 'incident_resolved',
                         f'异常 {inc.incident_no} 已处置：{resolution[:50]}', actor,
                         stop=inc.stop)
        remain = task.incidents.exclude(status=Incident.Status.RESOLVED).count()
        if remain == 0 and task.status == TaskStatus.ABNORMAL:
            # 未出发恢复「已派车」，已出发恢复「押运中」
            task.status = (TaskStatus.IN_TRANSIT if task.actual_depart
                           else TaskStatus.PLANNED)
            task.save(update_fields=['status', 'updated_at'])
            TaskService._log(
                task, 'resume',
                f'全部异常已处置，任务恢复{"押运" if task.actual_depart else "待出发"}',
                actor)
        return inc

    # ---------- 交接核对表 ----------
    @staticmethod
    def reconcile(task):
        rows = []
        for tb in (task.taskbox_set
                   .select_related('box', 'target_stop__branch')
                   .prefetch_related('handovers')):
            hs = list(tb.handovers.order_by('created_at'))
            phases = [h.phase for h in hs]
            seal_first = hs[0].seal_no_in if hs else ''
            seals = [h.seal_no_in for h in hs if h.seal_no_in]
            seal_chain_ok = len(set(seals)) == 1 if seals else False
            bad = [h.get_result_display() for h in hs
                   if h.result != Handover.Result.CONFIRMED]
            expected_phase = {
                'outbound': ['vault_out', 'branch_recv'],
                'inbound': ['branch_pickup', 'vault_return'],
            }[task.direction]
            phases_ok = all(p in phases for p in expected_phase) and \
                not any(p not in expected_phase for p in phases)
            rows.append({
                'box_no': tb.box.box_no,
                'box_type_display': tb.box.get_box_type_display(),
                'target_branch': tb.target_stop.branch.name,
                'sequence': tb.target_stop.sequence,
                'status': tb.status,
                'status_display': tb.get_status_display(),
                'seal_no': tb.seal_no,
                'seal_chain_ok': seal_chain_ok,
                'code_verified': any(h.code_verified for h in hs),
                'phases_done': [{'phase': p,
                                 'display': HandoverPhase(p).label} for p in phases],
                'phases_expected': [{'phase': p,
                                     'display': HandoverPhase(p).label}
                                    for p in expected_phase],
                'phases_complete': phases_ok,
                'exception_flag': tb.exception_flag,
                'problems': bad,
            })
        return {
            'task_no': task.task_no,
            'direction': task.direction,
            'total': len(rows),
            'all_clear': all(r['phases_complete'] and not r['problems']
                             and not r['exception_flag'] for r in rows),
            'rows': rows,
        }

    @staticmethod
    def _log(task, event, message, actor=None, stop=None, stop_id=None):
        if stop is None and stop_id:
            stop = task.stops.filter(id=stop_id).first()
        TaskLog.objects.create(task=task, stop=stop, event=event,
                               message=message, actor=actor)
