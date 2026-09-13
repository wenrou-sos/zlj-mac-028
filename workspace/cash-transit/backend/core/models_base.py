from django.db import models


class BranchType(models.TextChoices):
    HEAD_VAULT = 'head_vault', '中心金库'
    SUB_VAULT = 'sub_vault', '分金库'
    BRANCH = 'branch', '营业网点'
    SELF_BANK = 'self_bank', '自助银行'


class Branch(models.Model):
    """银行网点 / 金库（内置样例数据）。"""

    code = models.CharField('网点编号', max_length=20, unique=True)
    name = models.CharField('网点名称', max_length=100)
    short_name = models.CharField('简称', max_length=50, blank=True, default='')
    branch_type = models.CharField('类型', max_length=20,
                                   choices=BranchType.choices,
                                   default=BranchType.BRANCH)
    address = models.CharField('地址', max_length=200, blank=True, default='')
    contact_person = models.CharField('联系人', max_length=50, blank=True, default='')
    contact_phone = models.CharField('联系电话', max_length=20, blank=True, default='')
    lng = models.DecimalField('经度', max_digits=10, decimal_places=6, null=True)
    lat = models.DecimalField('纬度', max_digits=10, decimal_places=6, null=True)
    service_start = models.TimeField('营业开始', null=True, blank=True)
    service_end = models.TimeField('营业结束', null=True, blank=True)
    active = models.BooleanField('启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '网点/金库'
        verbose_name_plural = '网点/金库'
        ordering = ['code']

    def __str__(self):
        return f'{self.name}'

    @property
    def is_vault(self):
        return self.branch_type in (BranchType.HEAD_VAULT, BranchType.SUB_VAULT)


class Vehicle(models.Model):
    """押运车辆。"""

    class Status(models.TextChoices):
        IDLE = 'idle', '待命'
        ON_DUTY = 'on_duty', '执行任务'
        MAINTENANCE = 'maintenance', '维修中'

    plate = models.CharField('车牌号', max_length=20, unique=True)
    model = models.CharField('车型', max_length=50, default='防弹运钞车')
    capacity = models.PositiveIntegerField('核载款箱数', default=60)
    gps_device = models.CharField('GPS设备号', max_length=30, blank=True, default='')
    status = models.CharField('状态', max_length=20, choices=Status.choices,
                              default=Status.IDLE)
    home_branch = models.ForeignKey(Branch, verbose_name='驻停金库',
                                    on_delete=models.SET_NULL, null=True,
                                    related_name='vehicles')
    note = models.CharField('备注', max_length=200, blank=True, default='')

    class Meta:
        verbose_name = '押运车辆'
        verbose_name_plural = '押运车辆'
        ordering = ['plate']

    def __str__(self):
        return self.plate


class CashBox(models.Model):
    """实物款箱（尾箱 / 现金包 / 凭证箱）。"""

    class BoxType(models.TextChoices):
        TELLER = 'teller', '柜员尾箱'
        CASH = 'cash', '现金箱'
        VOUCHER = 'voucher', '凭证箱'
        ATM = 'atm', 'ATM加钞箱'

    class Status(models.TextChoices):
        IDLE = 'idle', '在库空闲'
        IN_TRANSIT = 'in_transit', '在途'
        DELIVERED = 'delivered', '已送达'

    box_no = models.CharField('款箱编号', max_length=30, unique=True)
    box_type = models.CharField('箱型', max_length=20, choices=BoxType.choices,
                                default=BoxType.TELLER)
    owner_branch = models.ForeignKey(Branch, verbose_name='归属网点',
                                     on_delete=models.PROTECT,
                                     related_name='boxes')
    cash_amount = models.DecimalField('面额合计(元)', max_digits=14,
                                      decimal_places=2, default=0)
    status = models.CharField('状态', max_length=20, choices=Status.choices,
                              default=Status.IDLE)
    note = models.CharField('备注', max_length=200, blank=True, default='')

    class Meta:
        verbose_name = '款箱'
        verbose_name_plural = '款箱'
        ordering = ['box_no']

    def __str__(self):
        return self.box_no


class Route(models.Model):
    """押运线路（模板，可复用于每日任务）。"""

    code = models.CharField('线路编号', max_length=20, unique=True)
    name = models.CharField('线路名称', max_length=100)
    depot = models.ForeignKey(Branch, verbose_name='出发金库',
                              on_delete=models.PROTECT, related_name='routes_out')
    distance_km = models.DecimalField('里程(公里)', max_digits=6,
                                      decimal_places=1, default=0)
    est_minutes = models.PositiveIntegerField('预计用时(分钟)', default=120)
    active = models.BooleanField('启用', default=True)
    note = models.CharField('备注', max_length=200, blank=True, default='')

    class Meta:
        verbose_name = '押运线路'
        verbose_name_plural = '押运线路'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'


class RouteStop(models.Model):
    route = models.ForeignKey(Route, verbose_name='线路',
                              on_delete=models.CASCADE, related_name='stops')
    sequence = models.PositiveIntegerField('顺序', default=1)
    branch = models.ForeignKey(Branch, verbose_name='停靠网点',
                               on_delete=models.PROTECT,
                               related_name='route_stops')
    planned_arrival = models.TimeField('计划到达时间', null=True, blank=True)
    dwell_minutes = models.PositiveIntegerField('停留(分钟)', default=15)

    class Meta:
        verbose_name = '线路停靠点'
        verbose_name_plural = '线路停靠点'
        unique_together = ('route', 'sequence')
        ordering = ['sequence']

    def __str__(self):
        return f'{self.route.code}-{self.sequence}.{self.branch.short_name or self.branch.name}'
