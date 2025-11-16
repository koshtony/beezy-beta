from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions, generics, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType

from approvals.models import ApprovalRecord, ApprovalFlow, Notification
from  approvals.serializers import ApprovalRecordSerializer, NotificationSerializer
from users.models import Employee


# =====================================================
# APPROVAL WORKFLOW VIEWSET
# =====================================================

class ApprovalViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    # -------------------------------------------------
    # Helper
    # -------------------------------------------------
    def _get_employee(self, request):
        """Resolve logged-in Employee from User."""
        employee = Employee.objects.filter(employee_code=request.user.username).first()
        if not employee:
            return None, Response({"error": "Employee profile not found."}, status=404)
        return employee, None

    # -------------------------------------------------
    # LIST & FILTERS
    # -------------------------------------------------
    def list(self, request):
        """List all approvals assigned to logged-in user."""
        employee, err = self._get_employee(request)
        if err:
            return err

        records = (
            ApprovalRecord.objects.filter(approver=employee)
            .select_related("approval_type", "creator", "approver")
            .order_by("-created_at")
        )
        return Response(ApprovalRecordSerializer(records, many=True).data)

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """List only pending approvals for logged-in user."""
        employee, err = self._get_employee(request)
        if err:
            return err

        records = (
            ApprovalRecord.objects.filter(approver=employee, status="pending")
            .select_related("approval_type", "creator", "approver")
            .order_by("level")
        )
        return Response(ApprovalRecordSerializer(records, many=True).data)

    @action(detail=False, methods=["get"], url_path="my-requests")
    def my_requests(self, request):
        """View approvals created by logged-in employee."""
        employee, err = self._get_employee(request)
        if err:
            return err

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
        """Approve a record and trigger next level if available."""
        employee, err = self._get_employee(request)
        if err:
            return err

        record = get_object_or_404(ApprovalRecord, pk=pk, approver=employee)

        if record.status != "pending":
            return Response({"error": "This approval has already been processed."}, status=400)

        # Mark this record as approved
        record.status = "approved"
        record.comment = request.data.get("comment", "")
        record.approved_at = timezone.now()
        record.save()

        approval_type = record.approval_type
        instance = record.content_object

        # Determine the next flow level
        next_flow = (
            ApprovalFlow.objects.filter(
                approval_type=approval_type,
                level__gt=record.level,
                is_active=True
            )
            .order_by("level")
            .first()
        )

        # If no next level, mark workflow complete
        if not next_flow:
            return Response(
                {"success": f"{approval_type.name} fully approved — workflow complete."},
                status=200
            )

        # Create the next approval record(s) automatically
        created_records = []

        if next_flow.approver:  # Now using direct approver field
            if not ApprovalRecord.objects.filter(
                approval_type=approval_type,
                content_type=ContentType.objects.get_for_model(instance),
                object_id=instance.id,
                approver=next_flow.approver,
                level=next_flow.level,
            ).exists():
                new_record = ApprovalRecord.objects.create(
                    approval_type=approval_type,
                    content_type=ContentType.objects.get_for_model(instance),
                    object_id=instance.id,
                    creator=record.creator,
                    approver=next_flow.approver,
                    level=next_flow.level,
                    status="pending" if next_flow.is_proper_approver else "notified",
                    is_proper_approver=next_flow.is_proper_approver,
                    was_notified=next_flow.notify_approver,
                )
                created_records.append(new_record)

        return Response(
            {
                "success": f"{approval_type.name} approved successfully.",
                "next_level": next_flow.level,
                "next_approver": next_flow.approver.full_name if next_flow.approver else None,
                "next_level_created": len(created_records),
            },
            status=200
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reject(self, request, pk=None):
        """Reject current record and stop further approvals."""
        employee, err = self._get_employee(request)
        if err:
            return err

        record = get_object_or_404(ApprovalRecord, pk=pk, approver=employee)

        if record.status != "pending":
            return Response({"error": "This approval has already been processed."}, status=400)

        # Reject
        record.status = "rejected"
        record.comment = request.data.get("comment", "")
        record.approved_at = timezone.now()
        record.save()

        # Cancel subsequent approvals
        ApprovalRecord.objects.filter(
            approval_type=record.approval_type,
            content_type=record.content_type,
            object_id=record.object_id,
            level__gt=record.level,
            status="pending"
        ).update(status="cancelled", comment="Auto-cancelled after rejection")

        return Response(
            {"success": f"{record.approval_type.name} rejected and workflow stopped."},
            status=200
        )

    # -------------------------------------------------
    # TRACK PROGRESS
    # -------------------------------------------------
    @action(detail=False, methods=["get"], url_path=r"progress/(?P<model_name>[^/.]+)/(?P<object_id>[0-9]+)")
    def progress(self, request, model_name=None, object_id=None):
        """Show progress and status per approval item."""
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
                "rejected" if rejected
                else "fully_approved" if approved == total else "in_progress"
            ),
            "records": ApprovalRecordSerializer(records, many=True).data,
        }
        return Response(progress)


# =====================================================
# NOTIFICATION API
# =====================================================

class NotificationListView(generics.ListAPIView):
    """List notifications for logged-in employee (searchable approver)."""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["recipient__full_name", "recipient__employee_code"]

    def get_queryset(self):
        employee = Employee.objects.filter(user=self.request.user).first()
        queryset = Notification.objects.filter(recipient=employee).order_by("-created_at")

        status_filter = self.request.query_params.get("status")
        if status_filter == "unread":
            queryset = queryset.filter(is_read=False)
        elif status_filter == "read":
            queryset = queryset.filter(is_read=True)

        return queryset


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def mark_notification_read(request, pk):
    """Mark notification as read."""
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
