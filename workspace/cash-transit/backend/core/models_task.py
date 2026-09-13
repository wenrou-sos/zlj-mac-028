import random
import string

from django.conf import settings
from django.db import models
from django.utils import timezone

from .models_base import Branch, CashBox, Route, RouteStop, Vehicle


class TaskStatus(models.TextChoices):
    DRAFT = 'draft', '草稿'
    PLANNED = 'planned', '已派车'
    IN_TRANSIT = 'in_transit', '押运中'
    ABNORMAL = 'abnormal', '异常挂起'
    COMPLETED = 'completed', '已完成'
    CANCELLED = 'cancelled', '已取消'


class StopStatus(models.TextChoices):
    PENDING = 'pending', '待到达'
    EN_ROUTE = 'en_route', '前往中'
    ARRIVED = 'arrived', '已到达'
    DONE = 'done', '交接完成'
    SKIPPED = 'skipped', '跳过'


class BoxTaskStatus(models.TextChoices):
    PENDING_OUT = 'pending_out', '待出库'
    IN_TRANSIT = 'in_transit', '在途'
    DELIVERED = 'delivered', '已送达网点'
    IN_RETURN = 'in_return', '返程在途'
    RETURNED = 'returned', '已回收入库'
    EXCEPTION = 'exception', '异常'


class TaskRole(models.TextChoices):
    CAR_CAPTAIN = 'car_captain', '车长'
    GUARD = 'guard', '押运员'
    DRIVER = 'driver', '驾驶员'


class Task(models.Model):
    """一次押运任务 = 一辆车 + 一条线路 + 若干人员 + 若干款箱。"""

    class Direction(models.TextChoices):
        OUTBOUND = 'outbound', '下解（金库→网点）'
        INBOUND = 'inbound', '上收（网点→金库）'

    task_no = models.CharField('任务编号', max_length=30, unique=True, editable=False)
    name = models.CharField('任务名称', max_length=100, blank=True, default='')
    direction = models.CharField('方向', max_length=10, choices=Direction.choices,
                                 default=Direction.OUTBOUND)
    route = models.ForeignKey(Route, verbose_name='押运线路',
                              on_delete=models.PROTECT, related_name='tasks')
    depot = models.ForeignKey(Branch, verbose_name='金库',
                              on_delete=models.PROTECT, related_name='depot_tasks')
    vehicle = models.ForeignKey(Vehicle, verbose_name='押运车辆',
                                on_delete=models.PROTECT, related_name='tasks')
    assignees = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                       through='TaskAssignee',
                                       verbose_name='随车人员')
    boxes = models.ManyToManyField(CashBox, through='TaskBox', verbose_name='款箱')
    planned_date = models.DateField('计划日期')
    planned_depart = models.TimeField('计划出发', null=True, blank=True)
    planned_return = models.TimeField('计划返回', null=True, blank=True)
    actual_depart = models.DateTimeField('实际出发', null=True, blank=True)
    actual_return = models.DateTimeField('实际返回', null=True, blank=True)
    status = models.CharField('状态', max_length=20, choices=TaskStatus.choices,
                              default=TaskStatus.DRAFT)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='创建人',
                                on_delete=models.PROTECT, related_name='created_tasks')
    notes = models.CharField('备注', max_length=300, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '押运任务'
        verbose_name_plural = '押运任务'
        ordering = ['-planned_date', '-created_at']

    def __str__(self):
        return self.task_no

    def save(self, *args, **kwargs):
        if not self.task_no:
            self.task_no = self.generate_task_no()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_task_no():
        today = timezone.localdate().strftime('%Y%m%d')
        prefix = f'YY-{today}-'
        exists = set(Task.objects.filter(task_no__startswith=prefix)
                     .values_list('task_no', flat=True))
        for seq in range(1, 100):
            candidate = f'{prefix}{seq:03d}'
            if candidate not in exists:
                return candidate
        return f'{prefix}{random.randint(100, 999)}'

    # ---- 进度辅助 ----
    @property
    def box_count(self):
        return self.taskbox_set.count()

    @property
    def handovered_count(self):
        if self.direction == Task.Direction.OUTBOUND:
            return self.taskbox_set.filter(
                status__in=[BoxTaskStatus.DELIVERED, BoxTaskStatus.IN_RETURN,
                            BoxTaskStatus.RETURNED]).count()
        return self.taskbox_set.filter(
            status__in=[BoxTaskStatus.RETURNED, BoxTaskStatus.IN_TRANSIT]).count()

    @property
    def finished_box_count(self):
        finished = (BoxTaskStatus.DELIVERED if self.direction == Task.Direction.OUTBOUND
                    else BoxTaskStatus.RETURNED)
        return self.taskbox_set.filter(status=finished).count()

    @property
    def total_amount(self):
        from django.db.models import Sum
        return self.taskbox_set.aggregate(
            total=Sum('box__cash_amount'))['total'] or 0


class TaskAssignee(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             verbose_name='人员')
    role_on_task = models.CharField('车上角色', max_length=20,
                                    choices=TaskRole.choices)

    class Meta:
        unique_together = ('task', 'user')
        verbose_name = '任务人员安排'

    def __str__(self):
        return f'{self.task.task_no}-{self.user.name}-{self.get_role_on_task_display()}'


class TaskStop(models.Model):
    task = models.ForeignKey(Task, verbose_name='任务', on_delete=models.CASCADE,
                             related_name='stops')
    sequence = models.PositiveIntegerField('顺序')
    branch = models.ForeignKey(Branch, verbose_name='停靠网点',
                               on_delete=models.PROTECT)
    planned_arrival = models.DateTimeField('计划到达', null=True, blank=True)
    actual_arrival = models.DateTimeField('实际到达', null=True, blank=True)
    actual_departure = models.DateTimeField('实际离开', null=True, blank=True)
    verify_code = models.CharField('交接验证码', max_length=6, blank=True, default='')
    status = models.CharField('状态', max_length=20, choices=StopStatus.choices,
                              default=StopStatus.PENDING)
    note = models.CharField('备注', max_length=200, blank=True, default='')

    class Meta:
        verbose_name = '任务停靠点'
        unique_together = ('task', 'sequence')
        ordering = ['sequence']

    def __str__(self):
        return f'{self.task.task_no}-{self.sequence}.{self.branch}'

    @staticmethod
    def generate_code():
        return ''.join(random.choices(string.digits[1:], k=4))


class TaskBox(models.Model):
    """任务中的款箱及其流转状态。"""

    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    box = models.ForeignKey(CashBox, verbose_name='款箱', on_delete=models.PROTECT)
    target_stop = models.ForeignKey(TaskStop, verbose_name='目标/来源停靠点',
                                    on_delete=models.CASCADE,
                                    related_name='task_boxes')
    status = models.CharField('流转状态', max_length=20,
                              choices=BoxTaskStatus.choices,
                              default=BoxTaskStatus.PENDING_OUT)
    seal_no = models.CharField('出库封签号', max_length=30, blank=True, default='')
    exception_flag = models.BooleanField('存在异常', default=False)

    class Meta:
        verbose_name = '任务款箱'
        unique_together = ('task', 'box')

    def __str__(self):
        return f'{self.task.task_no}-{self.box.box_no}'


class HandoverPhase(models.TextChoices):
    VAULT_OUT = 'vault_out', '金库出库'
    BRANCH_RECV = 'branch_recv', '网点接收'
    BRANCH_PICKUP = 'branch_pickup', '网点移交'
    VAULT_RETURN = 'vault_return', '金库回库'


class Handover(models.Model):
    """款箱交接记录（四阶段，逐箱登记，支持交接核对）。"""

    class Result(models.TextChoices):
        CONFIRMED = 'confirmed', '核对一致'
        SEAL_MISMATCH = 'seal_mismatch', '封签异常'
        CODE_MISMATCH = 'code_mismatch', '验证码不符'
        BOX_MISSING = 'box_missing', '款箱短少'

    task_box = models.ForeignKey(TaskBox, verbose_name='任务款箱',
                                 on_delete=models.CASCADE, related_name='handovers')
    phase = models.CharField('交接阶段', max_length=20,
                             choices=HandoverPhase.choices)
    stop = models.ForeignKey(TaskStop, verbose_name='停靠点',
                             on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='handovers')
    result = models.CharField('核对结果', max_length=20, choices=Result.choices,
                              default=Result.CONFIRMED)
    seal_no_out = models.CharField('交出方封签号', max_length=30, blank=True, default='')
    seal_no_in = models.CharField('接收方封签号', max_length=30, blank=True, default='')
    seal_intact = models.BooleanField('封签完好', default=True)
    code_verified = models.BooleanField('验证码核验', null=True, blank=True)
    from_person = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='交出人',
                                    on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='handovers_given')
    to_person = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='接收人',
                                  on_delete=models.PROTECT, null=True, blank=True,
                                  related_name='handovers_received')
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='登记人',
                                 on_delete=models.PROTECT,
                                 related_name='handovers_recorded')
    remark = models.CharField('备注', max_length=300, blank=True, default='')
    created_at = models.DateTimeField('交接时间', auto_now_add=True)

    class Meta:
        verbose_name = '款箱交接记录'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.task_box}-{self.get_phase_display()}'


class Incident(models.Model):
    """押运异常事件。"""

    class Category(models.TextChoices):
        TRAFFIC = 'traffic', '交通延误'
        SEAL = 'seal', '封签异常'
        BOX_DAMAGE = 'box_damage', '款箱破损'
        BOX_MISSING = 'box_missing', '款箱短少'
        PERSONNEL = 'personnel', '人员异常'
        VEHICLE = 'vehicle', '车辆故障'
        WEATHER = 'weather', '天气原因'
        SECURITY = 'security', '安全事件'
        OTHER = 'other', '其他'

    class Severity(models.TextChoices):
        LOW = 'low', '一般'
        MEDIUM = 'medium', '较重'
        HIGH = 'high', '严重'

    class Status(models.TextChoices):
        OPEN = 'open', '待处理'
        PROCESSING = 'processing', '处理中'
        RESOLVED = 'resolved', '已处置'

    incident_no = models.CharField('异常编号', max_length=30, unique=True, editable=False)
    task = models.ForeignKey(Task, verbose_name='任务', on_delete=models.CASCADE,
                             related_name='incidents')
    stop = models.ForeignKey(TaskStop, verbose_name='停靠点',
                             on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='incidents')
    task_box = models.ForeignKey(TaskBox, verbose_name='款箱',
                                 on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField('异常类型', max_length=20, choices=Category.choices)
    severity = models.CharField('严重程度', max_length=10, choices=Severity.choices,
                                default=Severity.LOW)
    description = models.TextField('情况描述')
    status = models.CharField('处理状态', max_length=20, choices=Status.choices,
                              default=Status.OPEN)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='上报人',
                                    on_delete=models.PROTECT,
                                    related_name='reported_incidents')
    created_at = models.DateTimeField('上报时间', auto_now_add=True)
    resolution = models.TextField('处置说明', blank=True, default='')
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='处置人',
                                    on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='resolved_incidents')
    resolved_at = models.DateTimeField('处置时间', null=True, blank=True)

    class Meta:
        verbose_name = '异常事件'
        ordering = ['-created_at']

    def __str__(self):
        return self.incident_no

    def save(self, *args, **kwargs):
        if not self.incident_no:
            today = timezone.localdate().strftime('%Y%m%d')
            n = Incident.objects.filter(
                incident_no__startswith=f'YC-{today}').count() + 1
            self.incident_no = f'YC-{today}-{n:03d}'
        super().save(*args, **kwargs)


class TaskLog(models.Model):
    """任务全程操作流水（用于时间轴追踪）。"""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='logs')
    stop = models.ForeignKey(TaskStop, on_delete=models.SET_NULL, null=True, blank=True)
    event = models.CharField('事件代码', max_length=40)
    message = models.CharField('内容', max_length=300)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                              null=True, blank=True, verbose_name='操作人')
    created_at = models.DateTimeField('时间', auto_now_add=True)

    class Meta:
        verbose_name = '任务日志'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.created_at:%H:%M:%S}] {self.message}'
