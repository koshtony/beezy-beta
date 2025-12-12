from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.views import StationViewSet, AttendanceViewSet,AttendanceClockView
from .web.views import attendance_list, attendance_dashboard,attendance_history

router = DefaultRouter()
router.register(r'stations', StationViewSet, basename='station')
router.register(r'attendance', AttendanceViewSet, basename='attendance')




urlpatterns = [
    path('', include(router.urls)),
    path("clock/", AttendanceClockView.as_view(), name="attendance-clock"),
    path("dashboard/", attendance_dashboard, name="attendance-dashboard"),
    path("history/<int:employee_id>/", attendance_history, name="attendance-history"),
    path("list/", attendance_list, name="attendance-list"),
    
]
