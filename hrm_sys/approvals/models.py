from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from users.models import Department, SubDepartment, Role, Employee
from django.apps import apps
import uuid

User = get_user_model()


class ApprovalType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    def __str__(self): return self.name


class ApprovalFlow(models.Model):
    approval_type = models.ForeignKey(ApprovalType, on_delete=models.CASCADE, related_name="flows")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    sub_department = models.ForeignKey(SubDepartment, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    level = models.PositiveIntegerField()
    is_proper_approver = models.BooleanField(default=True)
    notify_approver = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('approval_type', 'level')
        ordering = ["level"]

    def __str__(self):
        return f"{self.approval_type.name} - Level {self.level}"


# --------------------------------------------
# NOTIFICATIONS
# --------------------------------------------

class Notification(models.Model):
    recipient = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_record = models.ForeignKey("ApprovalRecord", on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Notification for {self.recipient.full_name}: {self.title}"


# --------------------------------------------
# APPROVAL RECORDS
# --------------------------------------------

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

    # Generic link to any model (like payment, expense, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    level = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    comment = models.TextField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    is_proper_approver = models.BooleanField(default=True)
    was_notified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --------------------------------------------
    # AUTO-NOTIFICATION TRIGGERS
    # --------------------------------------------

    def save(self, *args, **kwargs):
        new_record = self._state.adding  # True if just created
        previous_status = None
        if not new_record:
            old = ApprovalRecord.objects.get(pk=self.pk)
            previous_status = old.status

        super().save(*args, **kwargs)

        # NEW RECORD → Notify Approver
        if new_record and self.status == "pending":
            Notification.objects.create(
                recipient=self.approver,
                title=f"New {self.approval_type.name} Request",
                message=f"You have a new {self.approval_type.name} to review from {self.creator.full_name}.",
                related_record=self,
            )

        # STATUS CHANGED → Notify Creator
        elif previous_status != self.status and self.status in ["approved", "rejected"]:
            Notification.objects.create(
                recipient=self.creator,
                title=f"{self.approval_type.name} {self.status.capitalize()}",
                message=f"Your {self.approval_type.name} was {self.status} by {self.approver.full_name}.",
                related_record=self,
            )

    def __str__(self):
        return f"{self.approval_type.name} - {self.status} by {self.approver.full_name}"