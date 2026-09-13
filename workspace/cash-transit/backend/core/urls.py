from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (BranchViewSet, CashBoxViewSet, HandoverViewSet,
                    IncidentViewSet, RouteViewSet, StaffViewSet, TaskViewSet,
                    VehicleViewSet)

router = DefaultRouter()
router.register('branches', BranchViewSet, basename='branch')
router.register('vehicles', VehicleViewSet, basename='vehicle')
router.register('boxes', CashBoxViewSet, basename='box')
router.register('routes', RouteViewSet, basename='route')
router.register('staff', StaffViewSet, basename='staff')
router.register('tasks', TaskViewSet, basename='task')
router.register('incidents', IncidentViewSet, basename='incident')
router.register('handovers', HandoverViewSet, basename='handover')

urlpatterns = [
    path('', include(router.urls)),
]
