from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions,generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType

from .models import ApprovalRecord, ApprovalFlow, Notification
from .serializers import ApprovalRecordSerializer, NotificationSerializer
from users.models import Employee


class ApprovalViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """List all approvals assigned to the logged-in user (as approver)."""
        employee = get_object_or_404(Employee, employee_code=request.user.username)
        records = ApprovalRecord.objects.filter(approver=employee)
        serializer = ApprovalRecordSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """Fetch only pending approvals."""
        employee = get_object_or_404(Employee, employee_code=request.user.username)
        records = ApprovalRecord.objects.filter(approver=employee, status="pending")
        serializer = ApprovalRecordSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_requests(self, request):
        """View approvals created by the logged-in employee (their requests)."""
        employee = get_object_or_404(Employee, employee_code=request.user.username)
        records = ApprovalRecord.objects.filter(creator=employee).select_related("approval_type", "approver")
        serializer = ApprovalRecordSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def approve(self, request, pk=None):
        """Approve a record and move workflow to the next level."""
        employee = get_object_or_404(Employee, employee_code=request.user.username)
        record = get_object_or_404(ApprovalRecord, pk=pk, approver=employee)

        if record.status != "pending":
            return Response({"error": "This approval has already been processed."}, status=400)

        record.status = "approved"
        record.comment = request.data.get("comment", "")
        record.approved_at = timezone.now()
        record.save()

        self._progress_next(record)
        return Response({"success": f"{record.approval_type.name} approved successfully."})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Reject approval."""
        employee = get_object_or_404(Employee, employee_code=request.user.username)
        record = get_object_or_404(ApprovalRecord, pk=pk, approver=employee)

        if record.status != "pending":
            return Response({"error": "This approval has already been processed."}, status=400)

        record.status = "rejected"
        record.comment = request.data.get("comment", "")
        record.approved_at = timezone.now()
        record.save()

        return Response({"success": "Request rejected."})

    # -------------------------------------------------
    # 🧩 NEW: Approval Progress Tracking Endpoint
    # -------------------------------------------------
    @action(detail=False, methods=["get"], url_path="progress/(?P<model_name>[^/.]+)/(?P<object_id>[0-9]+)")
    def progress(self, request, model_name=None, object_id=None):
        """Return all approval records related to a specific object (for creator progress tracking)."""
        model = ContentType.objects.filter(model=model_name).first()
        if not model:
            return Response({"error": f"Invalid model name: {model_name}"}, status=400)

        records = (
            ApprovalRecord.objects.filter(content_type=model, object_id=object_id)
            .select_related("approver", "creator", "approval_type")
            .order_by("level", "created_at")
        )
        if not records.exists():
            return Response({"message": "No approval records found for this object."}, status=404)

        total = records.count()
        approved = records.filter(status="approved").count()
        rejected = records.filter(status="rejected").exists()

        progress = {
            "object_type": model.model,
            "object_id": object_id,
            "approval_type": records.first().approval_type.name,
            "total_steps": total,
            "approved_steps": approved,
            "progress_percent": round((approved / total) * 100, 1),
            "status": (
                "rejected"
                if rejected
                else "fully_approved" if approved == total else "in_progress"
            ),
            "records": ApprovalRecordSerializer(records, many=True).data,
        }

        return Response(progress)

    # -------------------------------------------------
    # Helper
    # -------------------------------------------------
    def _progress_next(self, record):
        """Move to next approval level."""
        approval_type = record.approval_type
        instance = record.content_object

        next_flows = ApprovalFlow.objects.filter(
            approval_type=approval_type, level__gt=record.level, is_active=True
        ).order_by("level")

        if not next_flows.exists():
            print(f"✅ {approval_type.name} fully approved.")
            return

        for flow in next_flows:
            approvers = Employee.objects.filter(
                department=flow.department,
                sub_department=flow.sub_department,
                job_position=flow.role.name if flow.role else None,
            )
            for approver in approvers:
                ApprovalRecord.objects.create(
                    approval_type=approval_type,
                    content_type=ContentType.objects.get_for_model(instance),
                    object_id=instance.id,
                    creator=record.creator,
                    approver=approver,
                    level=flow.level,
                    status="pending" if flow.is_proper_approver else "notified",
                    is_proper_approver=flow.is_proper_approver,
                    was_notified=flow.notify_approver,
                )
# List all notifications for the logged-in employee
class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        employee = Employee.objects.filter(user=self.request.user).first()
        return Notification.objects.filter(recipient=employee).order_by('-created_at')

# Mark a notification as read
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_notification_read(request, pk):
    try:
        employee = Employee.objects.filter(user=request.user).first()
        notif = Notification.objects.get(pk=pk, recipient=employee)
        notif.is_read = True
        notif.save()
        return Response({"message": "Notification marked as read"})
    except Notification.DoesNotExist:
        return Response({"error": "Notification not found"}, status=404)

# Get unread count
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def unread_count(request):
    employee = Employee.objects.filter(user=request.user).first()
    count = Notification.objects.filter(recipient=employee, is_read=False).count()
    return Response({"unread_count": count})