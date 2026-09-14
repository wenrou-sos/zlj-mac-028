"""岗位权限：动作级角色校验 + 任务数据可见范围。

角色约定（accounts.models.Role）：
- dispatcher 调度员：派车排班、资源状态维护、异常处置、全局查看
- vault_keeper 金库管理员：本金库的出库/回库交接
- guard 押运员（含车长 car_captain）：本任务到离站、网点交接、异常上报
- driver 驾驶员：仅查看本人任务，无操作权限
- branch_clerk 网点柜员：本网点任务与交接
- admin 系统管理员：全部放行
"""
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from accounts.models import Role

ROLE_LABEL = dict(Role.choices)

# 各业务动作允许的岗位
DISPATCH_ROLES = (Role.DISPATCHER, Role.ADMIN)
CREW_GUARD_ROLES_ON_TASK = ('car_captain', 'guard')


def is_admin(user):
    return bool(user and user.is_authenticated
                and (user.is_superuser or user.role == Role.ADMIN))


def require_roles(user, roles, action_name):
    """岗位校验，越权抛出带中文说明的 403。"""
    if not user.is_authenticated:
        raise PermissionDenied('请先登录后再操作')
    if is_admin(user):
        return
    if user.role not in roles:
        names = '、'.join(ROLE_LABEL.get(r, str(r)) for r in roles)
        raise PermissionDenied(
            f'「{action_name}」仅由{names}办理；您当前岗位为'
            f'「{user.get_role_display()}」，无权执行该操作')


def require_dispatcher(user, action_name='该操作'):
    require_roles(user, (Role.DISPATCHER,), action_name)


def task_crew_role(task, user):
    """返回该用户在任务中的车上角色，不在车组返回 None。"""
    if not user.is_authenticated:
        return None
    assignee = task.taskassignee_set.filter(user=user).first()
    return assignee.role_on_task if assignee else None


def require_task_captain(task, user, action_name='到离站操作'):
    if is_admin(user):
        return
    role_on_task = task_crew_role(task, user)
    if role_on_task != 'car_captain':
        if role_on_task:
            raise PermissionDenied(
                f'「{action_name}」由本任务车长办理，您在任务 '
                f'{task.task_no} 中的岗位是{role_on_task == "driver" and "驾驶员" or "押运员"}')
        raise PermissionDenied(
            f'您不在任务 {task.task_no} 车组中，无权{action_name}')


def require_incident_report(task, user):
    if is_admin(user):
        return
    if user.role == Role.DISPATCHER:
        return
    role_on_task = task_crew_role(task, user)
    if role_on_task in CREW_GUARD_ROLES_ON_TASK:
        return
    if role_on_task == 'driver':
        raise PermissionDenied('驾驶员不办理异常登记，请通知车长或调度员上报')
    raise PermissionDenied(
        f'只有调度员或任务 {task.task_no} 的随车押运人员可以上报异常')


# ---------- 交接环节权限 ----------

def can_record_phase(user, task, phase, stop=None):
    """返回 (bool, 原因)。"""
    if is_admin(user):
        return True, ''
    if phase in ('vault_out', 'vault_return'):
        if user.role != Role.VAULT_KEEPER:
            return False, ('金库出库/回库交接由金库管理员办理，'
                           f'您的岗位是「{user.get_role_display()}」')
        if user.branch_id != task.depot_id:
            return False, (f'该任务从{task.depot.name}出入库，'
                           f'您所属的是{user.branch.name if user.branch else "其他网点"}，'
                           '无权办理本次金库交接')
        return True, ''
    # 网点交接：本任务押运车组 或 本站网点柜员
    role_on_task = task_crew_role(task, user)
    if role_on_task in CREW_GUARD_ROLES_ON_TASK:
        return True, ''
    if user.role == Role.BRANCH_CLERK and stop is not None \
            and user.branch_id == stop.branch_id:
        return True, ''
    if role_on_task == 'driver':
        return False, '驾驶员不办理款箱交接'
    if user.role == Role.BRANCH_CLERK:
        return False, f'该停靠点不是您所属网点（{user.branch.name if user.branch else ""}）'
    return False, '网点交接由本任务车组与停靠网点柜员双人办理'


def require_record_phase(user, task, phase, stop=None):
    ok, reason = can_record_phase(user, task, phase, stop)
    if not ok:
        raise PermissionDenied(reason)


def validate_handover_people(task, phase, stop, from_person, to_person):
    """校验交接登记中交出人/接收人的岗位身份是否符合该环节。"""
    crew_roles = ('car_captain', 'guard')

    def is_keeper(u):
        return (u and u.role == Role.VAULT_KEEPER
                and u.branch_id == task.depot_id)

    def is_clerk(u):
        return (u and u.role == Role.BRANCH_CLERK and stop is not None
                and u.branch_id == stop.branch_id)

    def is_crew(u):
        if not u:
            return False
        a = task.taskassignee_set.filter(user=u).first()
        return bool(a and a.role_on_task in crew_roles)

    def label(u):
        return f'{u.name}（{u.get_role_display()}）' if u else '空'

    if phase == 'vault_out':
        if not is_keeper(from_person):
            raise PermissionDenied(f'交出人应为{task.depot.name}的金库管理员，当前为{label(from_person)}')
        if not is_crew(to_person):
            raise PermissionDenied(f'接收人应为任务车长，当前为{label(to_person)}')
    elif phase == 'vault_return':
        if not is_crew(from_person):
            raise PermissionDenied(f'交出人应为任务车长，当前为{label(from_person)}')
        if not is_keeper(to_person):
            raise PermissionDenied(f'接收人应为{task.depot.name}的金库管理员，当前为{label(to_person)}')
    elif phase == 'branch_recv':
        if not is_crew(from_person):
            raise PermissionDenied(f'交出人应为本任务车组押运人员，当前为{label(from_person)}')
        if not is_clerk(to_person):
            raise PermissionDenied(f'接收人应为{stop.branch.name}的网点柜员，当前为{label(to_person)}')
    elif phase == 'branch_pickup':
        if not is_clerk(from_person):
            raise PermissionDenied(f'交出人应为{stop.branch.name}的网点柜员，当前为{label(from_person)}')
        if not is_crew(to_person):
            raise PermissionDenied(f'接收人应为本任务车组押运人员，当前为{label(to_person)}')


# ---------- 数据可见范围 ----------

class IsDispatcher(BasePermission):
    """仅调度员 / 系统管理员可访问（排班调度与资源维护类接口）。"""

    message = '该功能仅调度员可用'

    def has_permission(self, request, view):
        user = request.user
        return bool(user.is_authenticated
                    and (is_admin(user) or user.role == Role.DISPATCHER))


def visible_tasks(qs, user):
    if not user.is_authenticated:
        return qs.none()
    if is_admin(user) or user.role == Role.DISPATCHER:
        return qs
    if user.role == Role.VAULT_KEEPER:
        return qs.filter(depot=user.branch) if user.branch_id else qs.none()
    if user.role in (Role.GUARD, Role.DRIVER):
        return qs.filter(assignees=user).distinct()
    if user.role == Role.BRANCH_CLERK:
        return qs.filter(stops__branch=user.branch).distinct() \
            if user.branch_id else qs.none()
    return qs.none()


def can_view_task(task, user):
    if is_admin(user) or user.role == Role.DISPATCHER:
        return True
    if user.role == Role.VAULT_KEEPER:
        return user.branch_id == task.depot_id
    if user.role in (Role.GUARD, Role.DRIVER):
        return task.taskassignee_set.filter(user=user).exists()
    if user.role == Role.BRANCH_CLERK:
        return task.stops.filter(branch=user.branch).exists()
    return False


def can_see_verify_code(task, stop, user):
    """交接验证码按最小知情范围开放。"""
    if not user.is_authenticated:
        return False
    if is_admin(user) or user.role == Role.DISPATCHER:
        return True
    # 随车押运人员（车长/押运员）：本站到达后可见
    if task_crew_role(task, user) in CREW_GUARD_ROLES_ON_TASK:
        return stop.status in ('arrived', 'done')
    # 本站柜员：仅自己网点、车辆到站后可见
    if user.role == Role.BRANCH_CLERK:
        return (user.branch_id == stop.branch_id
                and stop.status in ('arrived', 'done'))
    return False


def visible_handovers(qs, user):
    if not user.is_authenticated:
        return qs.none()
    if is_admin(user) or user.role == Role.DISPATCHER:
        return qs
    if user.role == Role.VAULT_KEEPER:
        return qs.filter(task_box__task__depot=user.branch).distinct() \
            if user.branch_id else qs.none()
    if user.role in (Role.GUARD, Role.DRIVER):
        return qs.filter(task_box__task__assignees=user).distinct()
    if user.role == Role.BRANCH_CLERK:
        return qs.filter(stop__branch=user.branch).distinct() \
            if user.branch_id else qs.none()
    return qs.none()


def visible_incidents(qs, user):
    if not user.is_authenticated:
        return qs.none()
    if is_admin(user) or user.role == Role.DISPATCHER:
        return qs
    if user.role == Role.VAULT_KEEPER:
        return qs.filter(task__depot=user.branch).distinct() \
            if user.branch_id else qs.none()
    if user.role in (Role.GUARD, Role.DRIVER):
        return qs.filter(task__assignees=user).distinct()
    if user.role == Role.BRANCH_CLERK:
        return qs.filter(task__stops__branch=user.branch).distinct() \
            if user.branch_id else qs.none()
    return qs.none()
