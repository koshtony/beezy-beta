from rest_framework.routers import DefaultRouter
from .views import (
    LeaveTypeViewSet, LeaveRequestViewSet, LeaveBalanceViewSet, LeaveApproverViewSet
)

router = DefaultRouter()
router.register(r'leave/types', LeaveTypeViewSet)
router.register(r'leave/requests', LeaveRequestViewSet)
router.register(r'leave/balances', LeaveBalanceViewSet)
router.register(r'leave/approvers', LeaveApproverViewSet)

urlpatterns = router.urls
