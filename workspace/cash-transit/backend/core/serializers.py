from rest_framework import serializers

from accounts.models import User

from .models import (Branch, CashBox, Handover, Incident, PersonnelStatusLog,
                     Route, RouteStop, Task, TaskAssignee, TaskBox, TaskLog,
                     TaskStop, Vehicle, VehicleStatusLog)
from .resource_service import ResourceService


# ---------- 基础档案 ----------

class BranchSerializer(serializers.ModelSerializer):
    branch_type_display = serializers.CharField(source='get_branch_type_display', read_only=True)
    is_vault = serializers.BooleanField(read_only=True)

    class Meta:
        model = Branch
        fields = ['id', 'code', 'name', 'short_name', 'branch_type',
                  'branch_type_display', 'is_vault', 'address', 'contact_person',
                  'contact_phone', 'lng', 'lat', 'service_start', 'service_end',
                  'active']


class VehicleSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    home_branch_name = serializers.CharField(source='home_branch.name', read_only=True,
                                             default='')
    busy_task_no = serializers.SerializerMethodField()
    schedulable = serializers.SerializerMethodField()
    unavailable_reason = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = ['id', 'plate', 'model', 'capacity', 'gps_device', 'status',
                  'status_display', 'home_branch', 'home_branch_name', 'note',
                  'busy_task_no', 'schedulable', 'unavailable_reason']

    def _on_date(self):
        request = self.context.get('request')
        return request.query_params.get('date') if request else None

    def get_busy_task_no(self, obj):
        busy = ResourceService.vehicle_busy_task(obj, self._on_date())
        return busy.task_no if busy else None

    def get_schedulable(self, obj):
        return ResourceService.vehicle_unavailable_reason(
            obj, self._on_date()) is None

    def get_unavailable_reason(self, obj):
        return ResourceService.vehicle_unavailable_reason(obj, self._on_date())


class CashBoxSerializer(serializers.ModelSerializer):
    box_type_display = serializers.CharField(source='get_box_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    owner_branch_name = serializers.CharField(source='owner_branch.name', read_only=True)

    class Meta:
        model = CashBox
        fields = ['id', 'box_no', 'box_type', 'box_type_display', 'owner_branch',
                  'owner_branch_name', 'cash_amount', 'status', 'status_display',
                  'note']


# ---------- 线路 ----------

class RouteStopSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    branch_short = serializers.CharField(
        source='branch.short_name', read_only=True, default='')
    lng = serializers.DecimalField(source='branch.lng', max_digits=10,
                                   decimal_places=6, read_only=True)
    lat = serializers.DecimalField(source='branch.lat', max_digits=10,
                                   decimal_places=6, read_only=True)

    class Meta:
        model = RouteStop
        fields = ['id', 'sequence', 'branch', 'branch_name', 'branch_short',
                  'lng', 'lat', 'planned_arrival', 'dwell_minutes']


class RouteListSerializer(serializers.ModelSerializer):
    depot_name = serializers.CharField(source='depot.name', read_only=True)
    stop_count = serializers.IntegerField(source='stops.count', read_only=True)

    class Meta:
        model = Route
        fields = ['id', 'code', 'name', 'depot', 'depot_name', 'stop_count',
                  'distance_km', 'est_minutes', 'active']


class RouteSerializer(RouteListSerializer):
    stops = RouteStopSerializer(many=True, read_only=True)

    class Meta(RouteListSerializer.Meta):
        fields = RouteListSerializer.Meta.fields + ['stops', 'note']


# ---------- 人员（简要） ----------

class UserBriefSerializer(serializers.ModelSerializer):
    """交接候选人简要信息（任务范围内可见）。"""
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    position_display = serializers.CharField(source='get_position_display', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True, default='')
    duty_display = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'name', 'employee_no', 'role', 'role_display',
                  'position', 'position_display', 'phone', 'branch',
                  'branch_name', 'active_duty', 'duty_display']


class StaffBriefSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    position_display = serializers.CharField(source='get_position_display', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True, default='')
    duty_display = serializers.CharField(read_only=True)
    busy_task_nos = serializers.SerializerMethodField()
    schedulable = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'name', 'employee_no', 'role', 'role_display',
                  'position', 'position_display', 'phone', 'branch',
                  'branch_name', 'active_duty', 'leave_type', 'duty_display',
                  'busy_task_nos', 'schedulable']

    def _on_date(self):
        request = self.context.get('request')
        return request.query_params.get('date') if request else None

    def get_busy_task_nos(self, obj):
        tasks = ResourceService.user_busy_tasks(obj)
        on_date = self._on_date()
        if on_date:
            tasks = [t for t in tasks if str(t.planned_date) == on_date]
        return [t.task_no for t in tasks][:5]

    def get_schedulable(self, obj):
        return ResourceService.user_unavailable_reason(
            obj, self._on_date()) is None


# ---------- 交接 / 异常 / 日志 ----------

class HandoverSerializer(serializers.ModelSerializer):
    phase_display = serializers.CharField(source='get_phase_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    from_person_name = serializers.CharField(source='from_person.name',
                                             read_only=True, default='')
    to_person_name = serializers.CharField(source='to_person.name',
                                           read_only=True, default='')
    operator_name = serializers.CharField(source='operator.name', read_only=True)
    box_no = serializers.CharField(source='task_box.box.box_no', read_only=True)

    class Meta:
        model = Handover
        fields = ['id', 'task_box', 'box_no', 'phase', 'phase_display', 'stop',
                  'result', 'result_display', 'seal_no_out', 'seal_no_in',
                  'seal_intact', 'code_verified', 'from_person', 'from_person_name',
                  'to_person', 'to_person_name', 'operator', 'operator_name',
                  'remark', 'created_at']
        read_only_fields = ['operator']


class IncidentSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reported_by_name = serializers.CharField(source='reported_by.name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.name',
                                             read_only=True, default='')
    task_no = serializers.CharField(source='task.task_no', read_only=True)
    box_no = serializers.CharField(source='task_box.box.box_no',
                                   read_only=True, default='')

    class Meta:
        model = Incident
        fields = ['id', 'incident_no', 'task', 'task_no', 'stop', 'task_box',
                  'box_no', 'category', 'category_display', 'severity',
                  'severity_display', 'description', 'status', 'status_display',
                  'reported_by', 'reported_by_name', 'created_at', 'resolution',
                  'resolved_by', 'resolved_by_name', 'resolved_at']
        read_only_fields = ['incident_no', 'reported_by', 'status', 'resolved_by',
                            'resolved_at']


class TaskLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.name', read_only=True, default='系统')

    class Meta:
        model = TaskLog
        fields = ['id', 'stop', 'event', 'message', 'actor', 'actor_name',
                  'created_at']


# ---------- 任务 ----------

class TaskAssigneeSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_employee_no = serializers.CharField(source='user.employee_no', read_only=True)
    user_phone = serializers.CharField(source='user.phone', read_only=True, default='')
    role_display = serializers.CharField(source='get_role_on_task_display', read_only=True)

    class Meta:
        model = TaskAssignee
        fields = ['id', 'user', 'user_name', 'user_employee_no', 'user_phone',
                  'role_on_task', 'role_display']


class TaskBoxSerializer(serializers.ModelSerializer):
    box_no = serializers.CharField(source='box.box_no', read_only=True)
    box_type = serializers.CharField(source='box.box_type', read_only=True)
    box_type_display = serializers.CharField(source='box.get_box_type_display',
                                             read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    cash_amount = serializers.DecimalField(source='box.cash_amount',
                                           max_digits=14, decimal_places=2,
                                           read_only=True)
    owner_branch_name = serializers.CharField(source='box.owner_branch.name',
                                              read_only=True)
    target_sequence = serializers.IntegerField(source='target_stop.sequence',
                                               read_only=True)
    last_handover = HandoverSerializer(source='handovers.first', read_only=True)

    class Meta:
        model = TaskBox
        fields = ['id', 'box', 'box_no', 'box_type', 'box_type_display',
                  'cash_amount', 'owner_branch_name', 'target_stop',
                  'target_sequence', 'status', 'status_display', 'seal_no',
                  'exception_flag', 'last_handover']


class TaskStopSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    branch_short = serializers.CharField(source='branch.short_name',
                                         read_only=True, default='')
    branch_type = serializers.CharField(source='branch.branch_type', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lng = serializers.DecimalField(source='branch.lng', max_digits=10,
                                   decimal_places=6, read_only=True)
    lat = serializers.DecimalField(source='branch.lat', max_digits=10,
                                   decimal_places=6, read_only=True)
    task_boxes = TaskBoxSerializer(many=True, read_only=True)

    class Meta:
        model = TaskStop
        fields = ['id', 'sequence', 'branch', 'branch_name', 'branch_short',
                  'branch_type', 'lng', 'lat', 'planned_arrival', 'actual_arrival',
                  'actual_departure', 'verify_code', 'status', 'status_display',
                  'note', 'task_boxes']


class TaskListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)
    route_name = serializers.CharField(source='route.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    depot_name = serializers.CharField(source='depot.short_name', read_only=True)
    box_count = serializers.IntegerField(read_only=True)
    finished_box_count = serializers.IntegerField(read_only=True)
    total_amount = serializers.DecimalField(max_digits=16, decimal_places=2,
                                            read_only=True)
    assignees_brief = serializers.SerializerMethodField()
    incident_open = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = ['id', 'task_no', 'name', 'direction', 'direction_display',
                  'route', 'route_name', 'depot', 'depot_name', 'vehicle',
                  'vehicle_plate',
                  'planned_date', 'planned_depart', 'planned_return',
                  'actual_depart', 'actual_return', 'status', 'status_display',
                  'box_count', 'finished_box_count', 'total_amount',
                  'assignees_brief', 'incident_open', 'created_at']

    def get_assignees_brief(self, obj):
        return [f'{a.user.name}({a.get_role_on_task_display()})'
                for a in obj.taskassignee_set.select_related('user')]

    def get_incident_open(self, obj):
        return obj.incidents.exclude(status=Incident.Status.RESOLVED).count()


class TaskDetailSerializer(TaskListSerializer):
    stops = TaskStopSerializer(many=True, read_only=True)
    assignees = TaskAssigneeSerializer(source='taskassignee_set', many=True,
                                       read_only=True)
    handovers = serializers.SerializerMethodField()
    incidents = IncidentSerializer(many=True, read_only=True)
    logs = TaskLogSerializer(many=True, read_only=True)
    creator_name = serializers.CharField(source='creator.name', read_only=True)
    notes = serializers.CharField()

    class Meta(TaskListSerializer.Meta):
        fields = TaskListSerializer.Meta.fields + [
            'stops', 'assignees', 'handovers', 'incidents', 'logs',
            'creator_name', 'notes', 'updated_at']

    def get_handovers(self, obj):
        qs = (Handover.objects.filter(task_box__task=obj)
              .select_related('from_person', 'to_person', 'operator',
                              'task_box__box')
              .order_by('created_at'))
        return HandoverSerializer(qs, many=True).data


class AssigneeInputSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role_on_task = serializers.ChoiceField(choices=['car_captain', 'guard', 'driver'])


class BoxInputSerializer(serializers.Serializer):
    box_id = serializers.IntegerField()
    target_stop_sequence = serializers.IntegerField(min_value=1)


class TaskCreateSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(choices=['outbound', 'inbound'],
                                        default='outbound')
    route_id = serializers.IntegerField()
    vehicle_id = serializers.IntegerField()
    planned_date = serializers.DateField()
    planned_depart = serializers.TimeField(required=False, allow_null=True)
    planned_return = serializers.TimeField(required=False, allow_null=True)
    name = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    assignees = AssigneeInputSerializer(many=True)
    boxes = BoxInputSerializer(many=True)

    def validate_assignees(self, value):
        if not value:
            raise serializers.ValidationError('至少安排一名随车人员')
        roles = [a['role_on_task'] for a in value]
        if 'car_captain' not in roles:
            raise serializers.ValidationError('必须指定一名车长')
        if 'driver' not in roles:
            raise serializers.ValidationError('必须指定一名驾驶员')
        if len({a['user_id'] for a in value}) != len(value):
            raise serializers.ValidationError('同一人员不能重复安排')
        return value

    def validate_boxes(self, value):
        if not value:
            raise serializers.ValidationError('至少分配一个款箱')
        if len({b['box_id'] for b in value}) != len(value):
            raise serializers.ValidationError('款箱不能重复')
        return value


# ---------- 任务动作入参 ----------

class ArriveStopSerializer(serializers.Serializer):
    stop_id = serializers.IntegerField()


class HandoverActionSerializer(serializers.Serializer):
    task_box_id = serializers.IntegerField()
    phase = serializers.ChoiceField(choices=['vault_out', 'branch_recv',
                                             'branch_pickup', 'vault_return'])
    stop_id = serializers.IntegerField(required=False)
    from_user_id = serializers.IntegerField(required=False)
    to_user_id = serializers.IntegerField(required=False)
    seal_no_in = serializers.CharField(required=False, allow_blank=True,
                                       default='')
    code = serializers.CharField(required=False, allow_blank=True, default='')
    seal_intact = serializers.BooleanField(required=False, default=True)
    remark = serializers.CharField(required=False, allow_blank=True, default='')


class IncidentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incident
        fields = ['stop', 'task_box', 'category', 'severity', 'description']


# ---------- 资源状态留痕 ----------

class VehicleStatusLogSerializer(serializers.ModelSerializer):
    from_status_display = serializers.SerializerMethodField()
    to_status_display = serializers.CharField(source='get_to_status_display',
                                              read_only=True)
    operator_name = serializers.CharField(source='operator.name',
                                          read_only=True, default='系统')
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)

    class Meta:
        model = VehicleStatusLog
        fields = ['id', 'vehicle', 'vehicle_plate', 'from_status',
                  'from_status_display', 'to_status', 'to_status_display',
                  'reason', 'task', 'operator', 'operator_name', 'created_at']

    def get_from_status_display(self, obj):
        return dict(Vehicle.Status.choices).get(obj.from_status, '')


class PersonnelStatusLogSerializer(serializers.ModelSerializer):
    leave_type_display = serializers.SerializerMethodField()
    operator_name = serializers.CharField(source='operator.name',
                                          read_only=True, default='系统')
    user_name = serializers.CharField(source='user.name', read_only=True)

    class Meta:
        model = PersonnelStatusLog
        fields = ['id', 'user', 'user_name', 'active_duty', 'leave_type',
                  'leave_type_display', 'reason', 'task', 'operator',
                  'operator_name', 'created_at']

    def get_leave_type_display(self, obj):
        if obj.active_duty:
            return '在岗'
        from accounts.models import LeaveType
        return dict(LeaveType.choices).get(obj.leave_type, '休息')
