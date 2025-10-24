from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StationViewSet, AttendanceViewSet,AttendanceClockView

router = DefaultRouter()
router.register(r'stations', StationViewSet, basename='station')
router.register(r'attendance', AttendanceViewSet, basename='attendance')




urlpatterns = [
    path('', include(router.urls)),
    path("clock/", AttendanceClockView.as_view(), name="attendance-clock"),
    
]
