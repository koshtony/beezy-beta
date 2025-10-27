from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ApprovalViewSet
from . import views

router = DefaultRouter()
router.register("approvals", ApprovalViewSet, basename="approval")

urlpatterns = [
    path("", include(router.urls)),
    path("notifications/", views.NotificationListView.as_view(), name="notification-list"),
    path("notifications/<int:pk>/read/", views.mark_notification_read, name="notification-mark-read"),
    path("notifications/unread-count/", views.unread_count, name="notification-unread-count"),
]
