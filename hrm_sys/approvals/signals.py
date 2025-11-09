from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import ApprovalRecord, ApprovalFlow, Notification
from users.models import Employee


@receiver(post_save, sender=ApprovalRecord)
def handle_approval_record_signal(sender, instance, created, **kwargs):
    """
    Handles notifications and workflow progression whenever an ApprovalRecord
    is created or updated.
    """

    # ------------------------------------------------------------
    # 1️⃣ NEW APPROVAL CREATED → Notify approver if pending
    # ------------------------------------------------------------
    if created and instance.status in ["pending", "notified"]:
        Notification.objects.create(
            recipient=instance.approver,
            title=f"New {instance.approval_type.name} Request",
            message=f"You have a new {instance.approval_type.name} request from {instance.creator.full_name}.",
            related_record=instance,
        )
        return  # Stop further processing for new records

    # ------------------------------------------------------------
    # 2️⃣ STATUS CHANGED → APPROVED / REJECTED → Notify creator
    # ------------------------------------------------------------
    if instance.status in ["approved", "rejected"]:
        Notification.objects.create(
            recipient=instance.creator,
            title=f"{instance.approval_type.name} {instance.status.capitalize()}",
            message=f"Your {instance.approval_type.name} was {instance.status} by {instance.approver.full_name}.",
            related_record=instance,
        )

    # ------------------------------------------------------------
    # 3️⃣ STATUS APPROVED → CREATE NEXT LEVEL APPROVAL RECORD(S)
    # ------------------------------------------------------------
    if instance.status == "approved":
        _create_next_level_records(instance)


# ------------------------------------------------------------
# INTERNAL HELPER FUNCTION
# ------------------------------------------------------------
def _create_next_level_records(record):
    """
    Create the next ApprovalRecord(s) for the next level(s) based on the
    ApprovalFlow configuration.
    """
    approval_type = record.approval_type
    instance = record.content_object

    # Get all next flows after the current level
    next_flows = (
        ApprovalFlow.objects.filter(
            approval_type=approval_type,
            level__gt=record.level,
            is_active=True,
        ).order_by("level")
    )

    if not next_flows.exists():
        print(f"✅ {approval_type.name} fully approved — workflow complete.")
        return

    for flow in next_flows:
        # Approver is directly set in the flow
        approver = flow.approver

        # Prevent duplicate records
        if ApprovalRecord.objects.filter(
            approval_type=approval_type,
            content_type=ContentType.objects.get_for_model(instance),
            object_id=instance.id,
            approver=approver,
            level=flow.level,
        ).exists():
            continue

        # Create new approval record
        new_record = ApprovalRecord.objects.create(
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

        # Notify the new approver
        Notification.objects.create(
            recipient=approver,
            title=f"New {approval_type.name} to review",
            message=f"You have a new {approval_type.name} request from {record.creator.full_name}.",
            related_record=new_record,
        )
