from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.views import LeaveRequestViewSet
from .web.views import leave_balances_view, approve_leave_action, pending_leaves_view

router = DefaultRouter()
router.register(r'requests', LeaveRequestViewSet, basename='leave-requests')

urlpatterns = [
    path('leave/', include(router.urls)), 
    path('leave_balances/', leave_balances_view, name='leave-balances'), 
    path('pending_leaves/', pending_leaves_view, name='pending-leaves'), 
    path("approve_leave/<int:leave_id>/", approve_leave_action, name="approve-leave-action"),
]
