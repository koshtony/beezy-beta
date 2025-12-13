from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from users.models import Employee
from approvals.models import ApprovalRecord, ApprovalType

# ==========================================================
# PAYROLL SETTINGS
# ==========================================================
class PayrollSetting(models.Model):
    paye_band_1_limit = models.DecimalField(max_digits=10, decimal_places=2, default=24000)
    paye_band_1_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    paye_band_2_limit = models.DecimalField(max_digits=10, decimal_places=2, default=40667)
    paye_band_2_rate = models.DecimalField(max_digits=5, decimal_places=2, default=25.00)
    paye_band_3_rate = models.DecimalField(max_digits=5, decimal_places=2, default=30.00)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_current(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

# ==========================================================
# PAYROLL PERIOD
# ==========================================================
MONTH_CHOICES = [(i, timezone.datetime(2000, i, 1).strftime('%B')) for i in range(1, 13)]

class PayrollPeriod(models.Model):
    month = models.IntegerField(choices=MONTH_CHOICES)
    year = models.IntegerField()
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("month", "year")

    def __str__(self):
        return f"{self.get_month_display()} {self.year}"

# ==========================================================
# ALLOWANCES
# ==========================================================
class Allowance(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_taxable = models.BooleanField(default=True)
    default_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.name

class EmployeeAllowance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="employee_allowances", null=True, blank=True)
    allowance = models.ForeignKey(Allowance, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    period_month = models.IntegerField(choices=MONTH_CHOICES, default=timezone.now().month)
    period_year = models.IntegerField(default=timezone.now().year)

    @property
    def is_taxable(self):
        return self.allowance.is_taxable

# ==========================================================
# DEDUCTIONS
# ==========================================================
class Deduction(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_statutory = models.BooleanField(default=False)
    apply_rate = models.BooleanField(default=False)
    rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    default_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def clean(self):
        if self.apply_rate and self.rate is None:
            raise ValidationError("Rate is required when apply_rate=True")

    def calculate_amount(self, gross_pay):
        if self.apply_rate:
            return (gross_pay * self.rate) / 100
        return self.default_amount or 0

    def __str__(self):
        return self.name

class EmployeeStatutoryDeduction(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="statutory_deductions", null=True, blank=True)
    deduction = models.ForeignKey(Deduction, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    period_month = models.IntegerField(choices=MONTH_CHOICES, default=timezone.now().month)
    period_year = models.IntegerField(default=timezone.now().year)

class EmployeeNonStatutoryDeduction(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="non_statutory_deductions", null=True, blank=True)
    deduction = models.ForeignKey(Deduction, on_delete=models.CASCADE,  null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    period_month = models.IntegerField(choices=MONTH_CHOICES, default=timezone.now().month)
    period_year = models.IntegerField(default=timezone.now().year)

# ==========================================================
# INCENTIVES
# ==========================================================
class Incentive(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="incentives")
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_taxable = models.BooleanField(default=True)
    period_month = models.IntegerField(choices=MONTH_CHOICES)
    period_year = models.IntegerField()

# ==========================================================
# OVERTIME
# ==========================================================
class OvertimeRecord(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="overtime_records", null=True, blank=True)
    period_month = models.IntegerField(choices=MONTH_CHOICES,default=timezone.now().month)
    period_year = models.IntegerField(default=timezone.now().year)
    standard_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    night_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    weekend_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    @property
    def total_amount(self):
        return (
            self.standard_hours * self.employee.overtime_rate +
            self.night_hours * self.employee.night_overtime_rate +
            self.weekend_hours * self.employee.weekend_overtime_rate
        )

# ==========================================================
# EMPLOYEE PAYROLL
# ==========================================================
class EmployeePayroll(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE)

    gross_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paye = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("employee", "period")

    def calculate_totals(self):
        if self.status != "draft":
            raise ValidationError("Only draft payrolls can be recalculated.")

        settings = PayrollSetting.get_current()

        # ------------------------------------------------------
        # Overtime
        # ------------------------------------------------------
        overtime_pay = sum(
            o.total_amount
            for o in self.employee.overtime_records.filter(
                period_month=self.period.month,
                period_year=self.period.year,
                status="approved"
            )
        )

        # ------------------------------------------------------
        # Allowances
        # ------------------------------------------------------
        total_allowances = sum(
            a.amount
            for a in self.employee.employee_allowances.filter(
                period_month=self.period.month,
                period_year=self.period.year
            )
        )
        taxable_allowances = sum(
            a.amount
            for a in self.employee.employee_allowances.filter(
                period_month=self.period.month,
                period_year=self.period.year,
                allowance__is_taxable=True
            )
        )

        # ------------------------------------------------------
        # Incentives
        # ------------------------------------------------------
        total_incentives = sum(
            i.amount
            for i in self.employee.incentives.filter(
                period_month=self.period.month,
                period_year=self.period.year
            )
        )
        taxable_incentives = sum(
            i.amount
            for i in self.employee.incentives.filter(
                period_month=self.period.month,
                period_year=self.period.year,
                is_taxable=True
            )
        )

        # ------------------------------------------------------
        # Gross pay (before deductions)
        # ------------------------------------------------------
        self.gross_pay = self.employee.basic_salary + total_allowances + total_incentives + overtime_pay

        # ------------------------------------------------------
        # Statutory deductions (excluding PAYE)
        # ------------------------------------------------------
        statutory_total = sum(
            d.calculate_amount(self.gross_pay)
            for d in self.employee.statutory_deductions.all()
        )

        # ------------------------------------------------------
        # Taxable pay for PAYE = (basic + taxable allowances + taxable incentives + overtime) - statutory deductions
        # ------------------------------------------------------
        taxable_pay = (
            self.employee.basic_salary
            + taxable_allowances
            + taxable_incentives
            + overtime_pay
            - statutory_total
        )

        # ------------------------------------------------------
        # PAYE
        # ------------------------------------------------------
        self.paye = self._calculate_paye(settings, taxable_pay)
        statutory_total += self.paye  # include PAYE in statutory total

        # ------------------------------------------------------
        # Non-statutory deductions
        # ------------------------------------------------------
        non_statutory_total = sum(
            d.amount
            for d in self.employee.non_statutory_deductions.filter(
                period_month=self.period.month,
                period_year=self.period.year
            )
        )

        # ------------------------------------------------------
        # Totals
        # ------------------------------------------------------
        self.total_deductions = statutory_total + non_statutory_total
        self.net_pay = self.gross_pay - self.total_deductions


    def _calculate_paye(self, settings, taxable_pay):
        pay = taxable_pay
        if pay <= settings.paye_band_1_limit:
            return pay * settings.paye_band_1_rate / 100
        elif pay <= settings.paye_band_2_limit:
            return (
                settings.paye_band_1_limit * settings.paye_band_1_rate / 100 +
                (pay - settings.paye_band_1_limit) * settings.paye_band_2_rate / 100
            )
        return (
            settings.paye_band_1_limit * settings.paye_band_1_rate / 100 +
            (settings.paye_band_2_limit - settings.paye_band_1_limit) * settings.paye_band_2_rate / 100 +
            (pay - settings.paye_band_2_limit) * settings.paye_band_3_rate / 100
        )

# ==========================================================
# BULK PAYROLL GENERATION
# ==========================================================
def bulk_generate_payroll(period: PayrollPeriod):
    created = 0
    skipped = 0
    employees = Employee.objects.filter(job_status="active")

    for emp in employees:
        payroll, is_created = EmployeePayroll.objects.get_or_create(
            employee=emp,
            period=period
        )
        if is_created:
            payroll.calculate_totals()
            payroll.save()
            created += 1
        else:
            skipped += 1

    return {"created": created, "skipped": skipped}
