from django.contrib import admin

from .models import (Branch, CashBox, Handover, Incident, Route, RouteStop,
                     Task, TaskAssignee, TaskBox, TaskLog, TaskStop, Vehicle)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'branch_type', 'contact_person',
                    'contact_phone', 'active')
    list_filter = ('branch_type', 'active')
    search_fields = ('code', 'name', 'address')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('plate', 'model', 'capacity', 'status', 'home_branch')
    list_filter = ('status',)
    search_fields = ('plate',)


@admin.register(CashBox)
class CashBoxAdmin(admin.ModelAdmin):
    list_display = ('box_no', 'box_type', 'owner_branch', 'cash_amount', 'status')
    list_filter = ('box_type', 'status')
    search_fields = ('box_no',)


class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 3


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'depot', 'distance_km', 'est_minutes', 'active')
    inlines = [RouteStopInline]
    search_fields = ('code', 'name')


class AssigneeInline(admin.TabularInline):
    model = TaskAssignee
    extra = 3


class StopInline(admin.TabularInline):
    model = TaskStop
    extra = 0


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('task_no', 'direction', 'route', 'vehicle', 'planned_date',
                    'status')
    list_filter = ('status', 'direction', 'planned_date')
    search_fields = ('task_no',)
    inlines = [AssigneeInline, StopInline]
    readonly_fields = ('task_no',)


@admin.register(Handover)
class HandoverAdmin(admin.ModelAdmin):
    list_display = ('id', 'task_box', 'phase', 'result', 'operator', 'created_at')
    list_filter = ('phase', 'result')


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('incident_no', 'task', 'category', 'severity', 'status',
                    'reported_by', 'created_at')
    list_filter = ('status', 'category', 'severity')


@admin.register(TaskLog)
class TaskLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'task', 'event', 'message', 'actor')
    list_filter = ('event',)
