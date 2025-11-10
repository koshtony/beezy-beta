from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from users.models import Employee
from approvals.models import ApprovalRecord, ApprovalType


# ==========================================================
#  SETTINGS MODEL — editable in admin
# ==========================================================
class PayrollSetting(models.Model):
    """Configurable payroll variables — editable via admin."""
    # PAYE bands
    paye_band_1_limit = models.DecimalField(max_digits=10, decimal_places=2, default=24000)
    paye_band_1_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.0)

    paye_band_2_limit = models.DecimalField(max_digits=10, decimal_places=2, default=40667)
    paye_band_2_rate = models.DecimalField(max_digits=5, decimal_places=2, default=25.0)

    paye_band_3_rate = models.DecimalField(max_digits=5, decimal_places=2, default=30.0)

    # Statutory rates (editable)
    nssf_rate = models.DecimalField(max_digits=5, decimal_places=2, default=6.0)  # % of gross
    nssf_cap = models.DecimalField(max_digits=10, decimal_places=2, default=2160.00)
    shif_rate = models.DecimalField(max_digits=5, decimal_places=2, default=2.75)  # % of gross
    housing_levy_rate = models.DecimalField(max_digits=5, decimal_places=2, default=1.50)  # % of gross

    # Overtime configuration
    overtime_hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=150.00,
        help_text="Default rate per overtime hour (KES)"
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payroll Setting"
        verbose_name_plural = "Payroll Settings"

    def __str__(self):
        return f"Payroll Settings (Last updated: {self.updated_at.date()})"

    @classmethod
    def get_current(cls):
        """Get latest settings, or create default if none."""
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


# ==========================================================
#  PERIOD MODEL
# ==========================================================
class PayrollPeriod(models.Model):
    MONTH_CHOICES = [(i, timezone.datetime(2000, i, 1).strftime('%B')) for i in range(1, 13)]

    month = models.IntegerField(choices=MONTH_CHOICES)
    year = models.IntegerField()
    is_locked = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('month', 'year')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.get_month_display()} {self.year}"


# ==========================================================
#  ALLOWANCES AND DEDUCTIONS
# ==========================================================
class Allowance(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_taxable = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Deduction(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_statutory = models.BooleanField(default=False)

    def __str__(self):
        return self.name


# ==========================================================
#  OVERTIME MODEL
# ==========================================================
class OvertimeRecord(models.Model):
    """Tracks overtime worked per employee per period."""
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='overtimes')
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='overtimes')
    hours_worked = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'period')

    def __str__(self):
        return f"{self.employee} - {self.hours_worked} hrs ({self.period})"

    @property
    def total_amount(self):
        return float(self.hours_worked) * float(self.hourly_rate)

    # ==============================================
    # Approval logic for overtime
    # ==============================================
    def submit_for_approval(self, creator):
        """Submit the overtime record for approval using the shared workflow."""
        approval_type = ApprovalType.objects.get(name="Overtime")

        # Prevent duplicate submissions
        existing = ApprovalRecord.objects.filter(
            approval_type=approval_type,
            object_id=self.id,
            content_type=ContentType.objects.get_for_model(self)
        )
        if existing.exists():
            return  # Already submitted

        ApprovalRecord.initialize_approvals(
            approval_type=approval_type,
            creator=creator,
            instance=self
        )
        self.status = "pending_approval"
        self.save(update_fields=["status"])

    def can_be_viewed(self, user):
        """Allow access if approved or the user is an approver."""
        if self.status == "approved":
            return True
        return ApprovalRecord.objects.filter(
            approver__user=user,
            object_id=self.id,
            content_type=ContentType.objects.get_for_model(self)
        ).exists()


# ==========================================================
#  PAYROLL MAIN MODEL
# ==========================================================
class EmployeePayroll(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='payrolls')
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    total_allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    gross_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paye = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shif = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    nssf = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    housing_levy = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'period')
        ordering = ['employee__full_name']

    def __str__(self):
        return f"{self.employee} - {self.period}"

    # ======================================================
    #  CALCULATIONS
    # ======================================================
    def calculate_totals(self):
        settings = PayrollSetting.get_current()
        self.overtime_pay = self.get_overtime_total()
        self.gross_pay = self.basic_salary + self.total_allowances + self.overtime_pay

        self.paye = self.calculate_paye(settings)
        self.shif = self.gross_pay * (settings.shif_rate / 100)
        self.nssf = min(self.gross_pay * (settings.nssf_rate / 100), settings.nssf_cap)
        self.housing_levy = self.gross_pay * (settings.housing_levy_rate / 100)

        total_deductions = (
            self.paye + self.shif + self.nssf + self.housing_levy + self.total_deductions
        )

        self.net_pay = self.gross_pay - total_deductions
        return self

    def calculate_paye(self, settings):
        """Progressive PAYE based on configured bands."""
        pay = self.gross_pay
        tax = 0

        if pay <= settings.paye_band_1_limit:
            tax = pay * (settings.paye_band_1_rate / 100)
        elif pay <= settings.paye_band_2_limit:
            tax = (
                settings.paye_band_1_limit * (settings.paye_band_1_rate / 100)
                + (pay - settings.paye_band_1_limit) * (settings.paye_band_2_rate / 100)
            )
        else:
            tax = (
                settings.paye_band_1_limit * (settings.paye_band_1_rate / 100)
                + (settings.paye_band_2_limit - settings.paye_band_1_limit)
                * (settings.paye_band_2_rate / 100)
                + (pay - settings.paye_band_2_limit) * (settings.paye_band_3_rate / 100)
            )

        return round(tax, 2)

    def get_overtime_total(self):
        """Sum of all approved overtime records for this employee & period."""
        overtimes = OvertimeRecord.objects.filter(employee=self.employee, period=self.period, status="approved")
        return sum(o.total_amount for o in overtimes)

    # ==============================================
    # Approval workflow integration
    # ==============================================
    def submit_for_approval(self, creator):
        """Submit the payroll record for approval using the shared workflow."""
        approval_type = ApprovalType.objects.get(name="Payroll")

        existing = ApprovalRecord.objects.filter(
            approval_type=approval_type,
            object_id=self.id,
            content_type=ContentType.objects.get_for_model(self)
        )
        if existing.exists():
            return  # Already under approval

        ApprovalRecord.initialize_approvals(
            approval_type=approval_type,
            creator=creator,
            instance=self
        )
        self.status = "pending_approval"
        self.save(update_fields=["status"])

    def can_be_viewed(self, user):
        """Restrict access to approved payrolls or approvers."""
        if self.status == "approved":
            return True
        return ApprovalRecord.objects.filter(
            approver__user=user,
            object_id=self.id,
            content_type=ContentType.objects.get_for_model(self)
        ).exists()


# ==========================================================
#  ALLOWANCE & DEDUCTION LINE ITEMS
# ==========================================================
class EmployeeAllowance(models.Model):
    employee_payroll = models.ForeignKey(EmployeePayroll, on_delete=models.CASCADE, related_name='allowances')
    allowance = models.ForeignKey(Allowance, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.allowance.name}: {self.amount}"


class EmployeeDeduction(models.Model):
    employee_payroll = models.ForeignKey(EmployeePayroll, on_delete=models.CASCADE, related_name='deductions')
    deduction = models.ForeignKey(Deduction, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.deduction.name}: {self.amount}"
