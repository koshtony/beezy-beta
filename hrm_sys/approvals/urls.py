from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.views import ApprovalViewSet
from .api import views as api_views
from .web import views as web_views

router = DefaultRouter()
router.register("approvals", ApprovalViewSet, basename="approval")

urlpatterns = [
    path("", include(router.urls)),
    path("notifications/", api_views.NotificationListView.as_view(), name="notification-list"),
    path("notifications/<int:pk>/read/",api_views.mark_notification_read, name="notification-mark-read"),
    path("notifications/unread-count/", api_views.unread_count, name="notification-unread-count"),
    
    path("create/", web_views.create_approval, name="create-approval"),
    path("load-approvers/", web_views.load_approvers, name="load-approvers"),
    path("approve/<int:record_id>/", web_views.approve_action, name="approve-action"),
    path("my-pending/", web_views.my_pending_approvals, name="my-pending-approvals"),
    path("approval-detail/<int:approval_id>/", web_views.approval_detail, name="approval-detail"),
    path("my-created/", web_views.my_created_approvals, name="my-created-approvals"),
    path("search-approvals/", web_views.search_my_created_approvals, name="search-my-created-approvals"),
    path("edit-approval/<int:approval_id>/", web_views.edit_approval, name="edit-approval"),
   
    
]