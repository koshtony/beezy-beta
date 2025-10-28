from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions, generics, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType

from .models import ApprovalRecord, ApprovalFlow, Notification
from .serializers import ApprovalRecordSerializer, NotificationSerializer
from users.models import Employee


# =====================================================
# APPROVAL WORKFLOW VIEWSET
# =====================================================

class ApprovalViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def _get_employee(self, request):
        """Helper to resolve logged-in Employee safely."""
        employee = Employee.objects.filter(employee_code=request.user.username).first()
        if not employee:
            return None, Response({"error": "Employee profile not found."}, status=404)
        return employee, None

    def list(self, request):
        """List all approvals assigned to the logged-in user (as approver)."""
        employee, err = self._get_employee(request)
        if err: return err

        records = (
            ApprovalRecord.objects.filter(approver=employee)
            .select_related("approval_type", "creator", "approver")
            .order_by("-created_at")
        )
        return Response(ApprovalRecordSerializer(records, many=True).data)

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """Fetch only pending approvals for the logged-in user."""
        employee, err = self._get_employee(request)
        if err: return err

        records = (
            ApprovalRecord.objects.filter(approver=employee, status="pending")
            .select_related("approval_type", "creator", "approver")
            .order_by("level")
        )
        return Response(ApprovalRecordSerializer(records, many=True).data)

    @action(detail=False, methods=["get"], url_path="my-requests")
    def my_requests(self, request):
        """View approvals created by the logged-in employee."""
        employee, err = self._get_employee(request)
        if err: return err

        records = (
            ApprovalRecord.objects.filter(creator=employee)
            .select_related("approval_type", "approver")
            .order_by("-created_at")
        )
        return Response(ApprovalRecordSerializer(records, many=True).data)

    # -------------------------------------------------
    # APPROVE / REJECT ACTIONS
    # -------------------------------------------------

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def approve(self, request, pk=None):
        """Approve a record and progress the workflow."""
        employee, err = self._get_employee(request)
        if err: return err

        record = get_object_or_404(ApprovalRecord, pk=pk, approver=employee)

        if record.status != "pending":
            return Response({"error": "This approval has already been processed."}, status=400)

        record.status = "approved"
        record.comment = request.data.get("comment", "")
        record.approved_at = timezone.now()
        record.save()

        # Move to next approval level if available
        self._progress_next(record)

        return Response({"success": f"{record.approval_type.name} approved successfully."}, status=200)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reject(self, request, pk=None):
        """Reject the approval request."""
        employee, err = self._get_employee(request)
        if err: return err

        record = get_object_or_404(ApprovalRecord, pk=pk, approver=employee)

        if record.status != "pending":
            return Response({"error": "This approval has already been processed."}, status=400)

        record.status = "rejected"
        record.comment = request.data.get("comment", "")
        record.approved_at = timezone.now()
        record.save()

        return Response({"success": f"{record.approval_type.name} rejected."}, status=200)

    # -------------------------------------------------
    # 🧩 PROGRESS TRACKER
    # -------------------------------------------------
    @action(detail=False, methods=["get"], url_path=r"progress/(?P<model_name>[^/.]+)/(?P<object_id>[0-9]+)")
    def progress(self, request, model_name=None, object_id=None):
        """Return approval progress for a specific object."""
        model = ContentType.objects.filter(model=model_name).first()
        if not model:
            return Response({"error": f"Invalid model name: {model_name}"}, status=400)

        records = (
            ApprovalRecord.objects.filter(content_type=model, object_id=object_id)
            .select_related("approval_type", "creator", "approver")
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
    # INTERNAL HELPER: Move to next level
    # -------------------------------------------------
    def _progress_next(self, record):
        """Create new approval records for the next flow level."""
        approval_type = record.approval_type
        instance = record.content_object

        next_flows = (
            ApprovalFlow.objects.filter(
                approval_type=approval_type,
                level__gt=record.level,
                is_active=True,
            )
            .order_by("level")
        )

        if not next_flows.exists():
            print(f"✅ {approval_type.name} fully approved — workflow complete.")
            return

        for flow in next_flows:
            approvers = Employee.objects.filter(
                department=flow.department,
                sub_department=flow.sub_department,
                role=flow.role,
            )
            for approver in approvers:
                # Prevent duplicate creation if already exists
                if ApprovalRecord.objects.filter(
                    approval_type=approval_type,
                    content_type=ContentType.objects.get_for_model(instance),
                    object_id=instance.id,
                    approver=approver,
                    level=flow.level,
                ).exists():
                    continue

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


# =====================================================
# NOTIFICATION API VIEWS
# =====================================================

class NotificationListView(generics.ListAPIView):
    """List notifications for logged-in employee."""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        employee = Employee.objects.filter(user=self.request.user).first()
        queryset = Notification.objects.filter(recipient=employee).order_by("-created_at")

        # Optional query filter: ?status=unread or ?status=read
        status_filter = self.request.query_params.get("status")
        if status_filter == "unread":
            queryset = queryset.filter(is_read=False)
        elif status_filter == "read":
            queryset = queryset.filter(is_read=True)

        return queryset


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def mark_notification_read(request, pk):
    """Mark a specific notification as read."""
    employee = Employee.objects.filter(user=request.user).first()
    notif = Notification.objects.filter(pk=pk, recipient=employee).first()
    if not notif:
        return Response({"error": "Notification not found."}, status=404)

    notif.is_read = True
    notif.save(update_fields=["is_read"])
    return Response({"message": "Notification marked as read."}, status=200)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def unread_count(request):
    """Return count of unread notifications."""
    employee = Employee.objects.filter(user=request.user).first()
    count = Notification.objects.filter(recipient=employee, is_read=False).count()
    return Response({"unread_count": count})
