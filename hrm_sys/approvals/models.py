from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from users.models import Department, SubDepartment, Role, Employee
from tinymce.models import HTMLField

User = get_user_model()


# =====================================================
# APPROVAL STRUCTURE
# =====================================================

class ApprovalType(models.Model):
    """Defines the type of approval, e.g., Leave, Expense, etc."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class ApprovalFlow(models.Model):
    """
    Defines the sequential approval levels for each approval type.
    Each level has an explicit approver (Employee).
    """
    approval_type = models.ForeignKey(ApprovalType, on_delete=models.CASCADE, related_name="flows")
    level = models.PositiveIntegerField()

    approver = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="flow_approver", help_text="The employee who should approve at this level"
    )

    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    sub_department = models.ForeignKey(SubDepartment, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)

    is_proper_approver = models.BooleanField(default=True)
    notify_approver = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('approval_type', 'level')
        ordering = ["level"]

    def __str__(self):
        return f"{self.approval_type.name} - Level {self.level} ({self.approver.full_name if self.approver else 'Unassigned'})"


# =====================================================
# NOTIFICATIONS
# =====================================================

class Notification(models.Model):
    recipient = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_record = models.ForeignKey("ApprovalRecord", on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Notification for {self.recipient.full_name}: {self.title}"


# =====================================================
# APPROVAL RECORDS
# =====================================================

class ApprovalRecord(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("notified", "Notified"),
    ]

    approval_type = models.ForeignKey(ApprovalType, on_delete=models.CASCADE)
    approver = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="approvals")
    creator = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="created_approvals")

    # Generic link to the object being approved
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, blank=True, null=True)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    content_object = GenericForeignKey("content_type", "object_id")

    level = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    comment = models.TextField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)

    is_proper_approver = models.BooleanField(default=True)
    was_notified = models.BooleanField(default=False)

    # Rich content & documents
    rich_content = HTMLField(blank=True, null=True)
  

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.approval_type.name} - {self.status} by {self.approver.full_name}"

    # =====================================================
    # METHODS
    # =====================================================

    @staticmethod
    def initialize_approvals(approval_type, creator, instance):
        """
        Auto-create first-level approvals based on ApprovalFlow setup.
        Called e.g. when a LeaveRequest is created.
        """
        from django.contrib.contenttypes.models import ContentType

        first_flows = ApprovalFlow.objects.filter(
            approval_type=approval_type,
            level=1,
            is_active=True
        )

        if not first_flows.exists():
            print(f"⚠️ No approval flow defined for {approval_type.name}")
            return

        for flow in first_flows:
            if not flow.approver:
                continue

            ApprovalRecord.objects.create(
                approval_type=approval_type,
                content_type=ContentType.objects.get_for_model(instance),
                object_id=instance.id,
                creator=creator,
                approver=flow.approver,
                level=flow.level,
                status="pending" if flow.is_proper_approver else "notified",
                is_proper_approver=flow.is_proper_approver,
                was_notified=flow.notify_approver,
            )

    def move_to_next_level(self):
        """
        Move to the next level automatically once approved.
        """
        from django.contrib.contenttypes.models import ContentType

        next_flow = ApprovalFlow.objects.filter(
            approval_type=self.approval_type,
            level=self.level + 1,
            is_active=True
        ).first()

        if not next_flow:
            # No more levels — mark the related record as fully approved
            instance = self.content_object
            if hasattr(instance, "status"):
                instance.status = "approved"
                instance.save(update_fields=["status"])
            return

        if not next_flow.approver:
            return

        ApprovalRecord.objects.create(
            approval_type=self.approval_type,
            content_type=ContentType.objects.get_for_model(self.content_object),
            object_id=self.object_id,
            creator=self.creator,
            approver=next_flow.approver,
            level=next_flow.level,
            status="pending" if next_flow.is_proper_approver else "notified",
            is_proper_approver=next_flow.is_proper_approver,
            was_notified=next_flow.notify_approver,
        )

def approval_attachment_path(instance, filename):
    """
    Returns a dynamic path for each approval's attachment:
    MEDIA_ROOT/approvals/<approval_id>/<filename>
    """
    return f"approvals/{instance.approval.id}/{filename}"

class ApprovalAttachment(models.Model):
    approval = models.ForeignKey('ApprovalRecord', on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=approval_attachment_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploadedby = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True)