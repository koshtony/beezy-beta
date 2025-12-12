from django.db import models
from django.utils import timezone
from users.models import Employee, Department, SubDepartment
import os


def attachment_upload_path(instance, filename):
    """Uploads leave attachments under employee folder"""
    return f"leave_attachments/{instance.employee.employee_code}/{filename}"


class LeaveType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    total_days_per_year = models.DecimalField(max_digits=5, decimal_places=1, default=0)

    def __str__(self):
        return f"{self.name}"


class LeaveBalance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_balances")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.PositiveIntegerField(default=timezone.now().year)
    allocated_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    used_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    remaining_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)

    class Meta:
        unique_together = ('employee', 'leave_type', 'year')

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.remaining_days} days left)"


class LeaveApprover(models.Model):
    """Defines approvers per department/subdepartment and approval order"""
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    subdepartment = models.ForeignKey(SubDepartment, on_delete=models.CASCADE, null=True, blank=True)
    approver = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="department_approvers")
    step = models.PositiveIntegerField(help_text="Approval order: 1=first, 2=second, etc.",null=True, blank=True)

    class Meta:
        ordering = ["step"]

    def __str__(self):
        return f"{self.approver.full_name} - {self.department} (Step {self.step})"


class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True, null=True)
    total_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    attachment = models.FileField(
        upload_to=attachment_upload_path,
        blank=True,
        null=True,
        help_text="Optional document (e.g. medical or travel proof)"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    current_step = models.PositiveIntegerField(default=1, help_text="Which approval step is active now")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.full_name} - {self.leave_type} ({self.status})"

    def save(self, *args, **kwargs):
        # ✅ Delete old attachment if replaced
        if self.pk:
            old = LeaveRequest.objects.filter(pk=self.pk).first()
            if old and old.attachment and old.attachment != self.attachment:
                if os.path.isfile(old.attachment.path):
                    os.remove(old.attachment.path)

        # ✅ Auto-calc total days
        if self.start_date and self.end_date:
            self.total_days = (self.end_date - self.start_date).days + 1

        super().save(*args, **kwargs)

        # ✅ Auto-create approval chain if new
        if not LeaveApprovalRecord.objects.filter(leave_request=self).exists():
            approvers = LeaveApprover.objects.filter(department=self.employee.department)
            if self.employee.sub_department:
                approvers = approvers.filter(
                    models.Q(subdepartment=self.employee.sub_department) | models.Q(subdepartment__isnull=True)
                )
            for a in approvers:
                LeaveApprovalRecord.objects.create(
                    leave_request=self,
                    approver=a.approver,
                    step=a.step,
                    action="pending"
                )

    def delete(self, *args, **kwargs):
        # ✅ Clean up attachment file
        if self.attachment and os.path.isfile(self.attachment.path):
            os.remove(self.attachment.path)
        super().delete(*args, **kwargs)


class LeaveApprovalRecord(models.Model):
    ACTION_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, related_name="approval_records")
    approver = models.ForeignKey(Employee, on_delete=models.CASCADE)
    step = models.PositiveIntegerField(null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default="pending")
    remarks = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["step"]

    def __str__(self):
        return f"Step {self.step} - {self.approver.full_name} ({self.action})"

    # ✅ Logic to approve a step
   # models.py
    def approve(self):
        self.action = "approved"
        self.timestamp = timezone.now()
        self.save()

        leave = self.leave_request
        remaining = leave.approval_records.filter(action="pending").order_by("step")

        if not remaining.exists():
            # ✅ All steps approved
            leave.status = "approved"
            leave.save()

            # ✅ Deduct from balance
            try:
                balance = LeaveBalance.objects.get(
                    employee=leave.employee,
                    leave_type=leave.leave_type,
                    year=leave.start_date.year
                )
                balance.used_days += leave.total_days
                balance.remaining_days = balance.allocated_days - balance.used_days
                balance.save()
            except LeaveBalance.DoesNotExist:
                # Optionally create a balance record if missing
                pass
        else:
            # Move to next step approver
            next_step = remaining.first().step
            leave.current_step = next_step
            leave.save()

    # ✅ Logic to reject a step
    def reject(self, remarks=None):
        self.action = "rejected"
        self.remarks = remarks or ""
        self.timestamp = timezone.now()
        self.save()

        leave = self.leave_request
        leave.status = "rejected"
        leave.save()


