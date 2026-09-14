from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import LeaveType, User

from .models import (Branch, CashBox, Handover, Incident, PersonnelStatusLog,
                     Route, RouteStop, Task, TaskAssignee, TaskBox, TaskLog,
                     TaskStop, Vehicle, VehicleStatusLog)
from .permissions import (IsDispatcher, can_view_task,
                          visible_handovers, visible_incidents, visible_tasks)
from .resource_service import ResourceService
from .serializers import (ArriveStopSerializer, BranchSerializer,
                          CashBoxSerializer, HandoverActionSerializer,
                          HandoverSerializer, IncidentCreateSerializer,
                          IncidentSerializer, PersonnelStatusLogSerializer,
                          RouteListSerializer, RouteSerializer,
                          StaffBriefSerializer, TaskCreateSerializer,
                          TaskDetailSerializer, TaskListSerializer,
                          UserBriefSerializer, VehicleSerializer,
                          VehicleStatusLogSerializer)
from .services import TaskService


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filterset_fields = ['branch_type', 'active']

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsDispatcher()]

    @action(detail=False)
    def vaults(self, request):
        qs = self.queryset.filter(
            branch_type__in=['head_vault', 'sub_vault'], active=True)
        return Response(BranchSerializer(qs, many=True).data)


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.select_related('home_branch').all()
    serializer_class = VehicleSerializer
    filterset_fields = ['status']

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsDispatcher()]

    @action(detail=True, methods=['post'], url_path='repair')
    def send_repair(self, request, pk=None):
        vehicle = self.get_object()
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({'detail': '请填写送修原因'},
                            status=status.HTTP_400_BAD_REQUEST)
        log = ResourceService.send_vehicle_repair(vehicle, reason, request.user)
        return Response({
            'vehicle': VehicleSerializer(vehicle).data,
            'log': VehicleStatusLogSerializer(log).data,
        })

    @action(detail=True, methods=['post'], url_path='return-service')
    def return_service(self, request, pk=None):
        vehicle = self.get_object()
        log = ResourceService.return_vehicle_service(vehicle, request.user)
        return Response({
            'vehicle': VehicleSerializer(vehicle).data,
            'log': VehicleStatusLogSerializer(log).data,
        })

    @action(detail=True, methods=['get'], url_path='status-logs')
    def status_logs(self, request, pk=None):
        vehicle = self.get_object()
        logs = vehicle.status_logs.select_related('operator', 'task')[:50]
        return Response(VehicleStatusLogSerializer(logs, many=True).data)


class CashBoxViewSet(viewsets.ModelViewSet):
    queryset = CashBox.objects.select_related('owner_branch').all()
    serializer_class = CashBoxSerializer
    filterset_fields = ['status', 'box_type', 'owner_branch']

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsDispatcher()]

    def get_queryset(self):
        qs = super().get_queryset()
        status_ = self.request.query_params.get('available')
        if status_ == '1':
            qs = qs.filter(status=CashBox.Status.IDLE)
        return qs


class RouteViewSet(viewsets.ModelViewSet):
    queryset = Route.objects.select_related('depot').prefetch_related('stops').all()
    filterset_fields = ['active']

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsDispatcher()]

    def get_serializer_class(self):
        if self.action == 'list':
            return RouteListSerializer
        return RouteSerializer


class StaffViewSet(viewsets.ReadOnlyModelViewSet):
    """人员档案：仅调度员/管理员可全量查看；任务交接候选人走 candidates 接口。"""
    permission_classes = [IsDispatcher]
    serializer_class = StaffBriefSerializer

    def get_queryset(self):
        qs = User.objects.filter(is_active=True).select_related('branch')
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)
        duty = self.request.query_params.get('duty')
        if duty == 'on':
            qs = qs.filter(active_duty=True)
        return qs.order_by('employee_no')

    @action(detail=True, methods=['post'], url_path='leave')
    def leave(self, request, pk=None):
        user = self.get_object()
        leave_type = request.data.get('leave_type') or 'rest'
        if leave_type not in dict(LeaveType.choices):
            return Response({'detail': '缺勤类型不合法'},
                            status=status.HTTP_400_BAD_REQUEST)
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({'detail': '请填写事由'},
                            status=status.HTTP_400_BAD_REQUEST)
        log = ResourceService.staff_leave(user, leave_type, reason, request.user)
        return Response({
            'staff': StaffBriefSerializer(user).data,
            'log': PersonnelStatusLogSerializer(log).data,
        })

    @action(detail=True, methods=['post'], url_path='return-duty')
    def return_duty(self, request, pk=None):
        user = self.get_object()
        log = ResourceService.staff_return(user, request.user)
        return Response({
            'staff': StaffBriefSerializer(user).data,
            'log': PersonnelStatusLogSerializer(log).data,
        })

    @action(detail=True, methods=['get'], url_path='duty-logs')
    def duty_logs(self, request, pk=None):
        user = self.get_object()
        logs = user.duty_logs.select_related('operator')[:50]
        return Response(PersonnelStatusLogSerializer(logs, many=True).data)


class TaskViewSet(viewsets.ModelViewSet):
    queryset = (Task.objects.select_related('route', 'vehicle', 'depot', 'creator')
                .prefetch_related('taskassignee_set__user').all())

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return TaskCreateSerializer
        if self.action == 'list':
            return TaskListSerializer
        return TaskDetailSerializer

    def get_queryset(self):
        qs = visible_tasks(super().get_queryset(), self.request.user)
        params = self.request.query_params
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if params.get('direction'):
            qs = qs.filter(direction=params['direction'])
        if params.get('date'):
            qs = qs.filter(planned_date=params['date'])
        if params.get('vehicle'):
            qs = qs.filter(vehicle_id=params['vehicle'])
        if params.get('keyword'):
            qs = qs.filter(task_no__icontains=params['keyword'])
        return qs

    def _get_task_or_deny(self, pk):
        task = Task.objects.filter(pk=pk).first()
        if task is None:
            return None
        if not can_view_task(task, self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                f'任务 {task.task_no} 不在您的职责范围：'
                '调度员查看全部、金库管理员看本金库、车组看本人任务、'
                '网点柜员看本网点任务')
        return task

    def retrieve(self, request, pk=None):
        task = self._get_task_or_deny(pk)
        if task is None:
            return Response({'detail': '任务不存在'}, status=404)
        return Response(TaskDetailSerializer(task).data)

    def create(self, request, *args, **kwargs):
        # 服务层做岗位校验（错误信息更具体）
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = TaskService.create_task(serializer.validated_data, request.user)
        return Response(TaskDetailSerializer(task).data,
                        status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        return Response({'detail': '任务创建后请使用流转操作，不支持整体修改'},
                        status=status.HTTP_405_METHOD_NOT_ALLOWED)

    # ---- 仪表盘（调度员） ----
    @action(detail=False, permission_classes=[IsDispatcher])
    def dashboard(self, request):
        from django.db.models import Count
        qs = Task.objects.all()
        by_status = {row['status']: row['n'] for row in
                     qs.values('status').annotate(n=Count('id'))}
        from django.utils import timezone
        today = request.query_params.get('date') or timezone.localdate().isoformat()
        today_qs = qs.filter(planned_date=today)
        open_inc = Incident.objects.exclude(status=Incident.Status.RESOLVED).count()
        recent = TaskListSerializer(qs.select_related('route', 'vehicle')[:8], many=True)
        return Response({
            'by_status': by_status,
            'today_total': today_qs.count(),
            'today_in_transit': today_qs.filter(
                status__in=['in_transit', 'abnormal']).count(),
            'vehicles_on_duty': Vehicle.objects.filter(
                status=Vehicle.Status.ON_DUTY).count(),
            'open_incidents': open_inc,
            'recent': recent.data,
        })

    # ---- 交接候选人（仅任务相关人员可查） ----
    @action(detail=True, methods=['get'], url_path='handover-candidates')
    def handover_candidates(self, request, pk=None):
        task = self._get_task_or_deny(pk)
        if task is None:
            return Response({'detail': '任务不存在'}, status=404)
        phase = request.query_params.get('phase')
        captains = [a.user for a in
                    task.taskassignee_set.select_related('user')
                    .filter(role_on_task='car_captain')]
        data = {}
        if phase in ('vault_out', 'vault_return'):
            keepers = User.objects.filter(
                role='vault_keeper', is_active=True, active_duty=True,
                branch=task.depot)
            crew = [a.user for a in
                    task.taskassignee_set.select_related('user')
                    .filter(role_on_task='car_captain')]
            if phase == 'vault_out':
                data = {'from_users': UserBriefSerializer(keepers, many=True).data,
                        'to_users': UserBriefSerializer(crew, many=True).data}
            else:
                data = {'from_users': UserBriefSerializer(crew, many=True).data,
                        'to_users': UserBriefSerializer(keepers, many=True).data}
        elif phase in ('branch_recv', 'branch_pickup'):
            stop_id = request.query_params.get('stop_id')
            stop = task.stops.filter(id=stop_id).first()
            clerks = User.objects.none()
            if stop:
                clerks = User.objects.filter(
                    role='branch_clerk', is_active=True, active_duty=True,
                    branch=stop.branch)
            crew = [a.user for a in
                    task.taskassignee_set.select_related('user')
                    .filter(role_on_task__in=['car_captain', 'guard'])]
            if phase == 'branch_recv':
                data = {'from_users': UserBriefSerializer(crew, many=True).data,
                        'to_users': UserBriefSerializer(clerks, many=True).data}
            else:
                data = {'from_users': UserBriefSerializer(clerks, many=True).data,
                        'to_users': UserBriefSerializer(crew, many=True).data}
        return Response(data)

    # ---- 流转动作 ----
    def _action_task(self, request, pk):
        return self._get_task_or_deny(pk)

    @action(detail=True, methods=['post'])
    def depart(self, request, pk=None):
        task = self._action_task(request, pk)
        TaskService.depart(task, request.user)
        return Response(TaskDetailSerializer(task).data)

    @action(detail=True, methods=['post'], url_path='arrive')
    def arrive(self, request, pk=None):
        task = self._action_task(request, pk)
        ser = ArriveStopSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        TaskService.arrive_stop(task, ser.validated_data['stop_id'], request.user)
        return Response(TaskDetailSerializer(task).data)

    @action(detail=True, methods=['post'], url_path='handover')
    def handover(self, request, pk=None):
        task = self._action_task(request, pk)
        ser = HandoverActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        h = TaskService.handover(task, ser.validated_data, request.user)
        return Response({
            'handover': HandoverSerializer(h).data,
            'task': TaskDetailSerializer(task).data,
        })

    @action(detail=True, methods=['post'], url_path='finish-stop')
    def finish_stop(self, request, pk=None):
        task = self._action_task(request, pk)
        ser = ArriveStopSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        TaskService.finish_stop(task, ser.validated_data['stop_id'], request.user)
        return Response(TaskDetailSerializer(task).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        task = self._action_task(request, pk)
        TaskService.complete(task, request.user)
        return Response(TaskDetailSerializer(task).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        task = self._action_task(request, pk)
        TaskService.cancel(task, request.user, request.data.get('reason', ''))
        return Response(TaskDetailSerializer(task).data)

    # ---- 异常 ----
    @action(detail=True, methods=['get', 'post'], url_path='incidents')
    def incidents(self, request, pk=None):
        task = self._action_task(request, pk)
        if request.method == 'POST':
            ser = IncidentCreateSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            inc = TaskService.report_incident(task, ser.validated_data, request.user)
            return Response(IncidentSerializer(inc).data,
                            status=status.HTTP_201_CREATED)
        return Response(IncidentSerializer(task.incidents.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='incidents/(?P<incident_id>[0-9]+)/resolve')
    def resolve_incident(self, request, pk=None, incident_id=None):
        task = self._action_task(request, pk)
        resolution = (request.data.get('resolution') or '').strip()
        if not resolution:
            return Response({'detail': '请填写处置说明'},
                            status=status.HTTP_400_BAD_REQUEST)
        TaskService.resolve_incident(task, incident_id, request.user, resolution)
        return Response(TaskDetailSerializer(task).data)

    # ---- 交接核对表 ----
    @action(detail=True, methods=['get'])
    def reconcile(self, request, pk=None):
        task = self._action_task(request, pk)
        return Response(TaskService.reconcile(task))

    # ---- 全程日志 ----
    @action(detail=True)
    def timeline(self, request, pk=None):
        task = self._action_task(request, pk)
        logs = task.logs.select_related('actor', 'stop').all()[:100]
        from .serializers import TaskLogSerializer
        return Response(TaskLogSerializer(logs, many=True).data)


class IncidentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (Incident.objects.select_related('task', 'reported_by', 'task_box__box')
                .all())
    serializer_class = IncidentSerializer
    filterset_fields = ['status', 'category', 'severity']

    def get_queryset(self):
        return visible_incidents(super().get_queryset(), self.request.user)


class HandoverViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (Handover.objects.select_related('task_box__box', 'from_person',
                                                'to_person', 'operator').all())
    serializer_class = HandoverSerializer
    filterset_fields = ['phase', 'result']

    def get_queryset(self):
        return visible_handovers(super().get_queryset(), self.request.user)


SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')
