from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StationViewSet, AttendanceViewSet

router = DefaultRouter()
router.register(r'stations', StationViewSet, basename='station')
router.register(r'attendance', AttendanceViewSet, basename='attendance')


urlpatterns = [
    path('', include(router.urls)),
]
