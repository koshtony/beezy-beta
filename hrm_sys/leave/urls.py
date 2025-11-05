from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LeaveRequestViewSet

router = DefaultRouter()
router.register(r'requests', LeaveRequestViewSet, basename='leave-requests')

urlpatterns = [
    path('leave/', include(router.urls)),  # ✅ matches Flutter baseUrl: /leave/leave/
]
