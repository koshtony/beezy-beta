from django.db import models
from django.conf import settings
from django.utils import timezone
from users.models import Employee, Department, SubDepartment  # adjust import paths as needed


class LeaveType(models.Model):
    """Defines leave categories and their yearly allocation"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    total_days_per_year = models.DecimalField(max_digits=5, decimal_places=1, default=0)

    def __str__(self):
        return f"{self.name} ({self.total_days_per_year} days)"


class LeaveBalance(models.Model):
    """Tracks remaining leave days for each employee per leave type"""
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
    """Maps department/subdepartment to approvers"""
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    subdepartment = models.ForeignKey(SubDepartment, on_delete=models.CASCADE, blank=True, null=True)
    approver = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_approvers')

    def __str__(self):
        return f"Approver: {self.approver} for {self.department}/{self.subdepartment or '-'}"


class LeaveRequest(models.Model):
    """Stores leave applications made by employees"""
    DAY_TYPE_CHOICES = [
        ('full', 'Full Day'),
        ('half', 'Half Day'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    day_type = models.CharField(max_length=10, choices=DAY_TYPE_CHOICES, default='full')
    total_days = models.DecimalField(max_digits=5, decimal_places=1)
    reason = models.TextField(blank=True, null=True)
    attachment = models.FileField(
        upload_to="leave_attachments/",
        blank=True,
        null=True,
        help_text="Optional supporting document (e.g. medical or travel document)"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approver = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, blank=True, null=True, related_name="approved_leaves"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Automatically calculate total days
        if self.start_date and self.end_date:
            days = (self.end_date - self.start_date).days + 1
            self.total_days = days - 0.5 if self.day_type == 'half' else days
        super().save(*args, **kwargs)

    def approve(self, approver):
        """Approve leave and deduct days automatically"""
        self.status = 'approved'
        self.approver = approver
        self.save()

        # Deduct days from balance
        balance, created = LeaveBalance.objects.get_or_create(
            employee=self.employee,
            leave_type=self.leave_type,
            defaults={'allocated_days': self.leave_type.total_days_per_year,'remaining_days': 0 ,'used_days': 0}
        )
        balance.used_days += self.total_days
        balance.remaining_days -= self.total_days	
        balance.save()

    def reject(self, approver):
        """Reject leave request"""
        self.status = 'rejected'
        self.approver = approver
        self.save()

class LeaveApprovalRecord(models.Model):
    ACTION_CHOICES = [
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, related_name="records")
    approver = models.ForeignKey(Employee, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    remarks = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.leave_request.id} - {self.approver.full_name} {self.action}"