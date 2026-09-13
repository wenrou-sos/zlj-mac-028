from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    DISPATCHER = 'dispatcher', '调度员'
    GUARD = 'guard', '押运员'
    DRIVER = 'driver', '驾驶员'
    BRANCH_CLERK = 'branch_clerk', '网点柜员'
    VAULT_KEEPER = 'vault_keeper', '金库管理员'
    ADMIN = 'admin', '系统管理员'


class Position(models.TextChoices):
    CAR_CAPTAIN = 'car_captain', '车长'
    ESCORT_GUARD = 'escort_guard', '武装押运员'
    DRIVER = 'driver', '驾驶员'
    DISPATCHER = 'dispatcher', '调度员'
    VAULT_KEEPER = 'vault_keeper', '金库管理员'
    CLERK = 'clerk', '网点柜员'


class User(AbstractUser):
    """系统用户，同时也是押运参与人员档案。"""

    employee_no = models.CharField('工号', max_length=20, unique=True)
    name = models.CharField('姓名', max_length=50)
    role = models.CharField('角色', max_length=20, choices=Role.choices,
                            default=Role.GUARD)
    position = models.CharField('岗位', max_length=20, choices=Position.choices,
                                blank=True, default='')
    phone = models.CharField('联系电话', max_length=20, blank=True, default='')
    id_card = models.CharField('身份证号', max_length=18, blank=True, default='')
    branch = models.ForeignKey(
        'core.Branch', verbose_name='所属网点/金库',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='staff',
    )
    active_duty = models.BooleanField('今日在岗', default=True)

    class Meta:
        verbose_name = '用户/人员'
        verbose_name_plural = '用户/人员'
        ordering = ['employee_no']

    def __str__(self):
        return f'{self.name}({self.employee_no})'

    @property
    def role_display(self):
        return self.get_role_display()

    @property
    def is_office_staff(self):
        """调度/金库/管理员等后台角色。"""
        return self.role in (Role.DISPATCHER, Role.VAULT_KEEPER, Role.ADMIN)
