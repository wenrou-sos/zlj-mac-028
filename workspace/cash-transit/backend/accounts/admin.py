from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('employee_no', 'name', 'role', 'position', 'phone', 'active_duty')
    list_filter = ('role', 'position', 'active_duty')
    search_fields = ('employee_no', 'name', 'username', 'phone')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('押运档案', {'fields': ('employee_no', 'name', 'role', 'position',
                              'phone', 'id_card', 'branch', 'active_duty')}),
    )
