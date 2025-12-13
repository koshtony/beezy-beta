from django.contrib import admin, messages
from .models import (
    PayrollSetting, PayrollPeriod,
    Allowance, EmployeeAllowance,
    Deduction, EmployeeStatutoryDeduction, EmployeeNonStatutoryDeduction,
    Incentive, OvertimeRecord,
    EmployeePayroll,bulk_generate_payroll
)

# ==========================================================
# PAYROLL SETTINGS
# ==========================================================
@admin.register(PayrollSetting)
class PayrollSettingAdmin(admin.ModelAdmin):
    list_display = ('id', 'paye_band_1_limit', 'paye_band_1_rate', 
                    'paye_band_2_limit', 'paye_band_2_rate', 'paye_band_3_rate', 'updated_at')


# ==========================================================
# PAYROLL PERIOD
# ==========================================================
@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ('month', 'year', 'is_locked', 'created_at')
    list_filter = ('year', 'month', 'is_locked')
    ordering = ('-year', '-month')
    search_fields = ('month', 'year')

    actions = ['generate_payroll_for_period']

    def generate_payroll_for_period(self, request, queryset):
        """
        Custom action to generate payrolls for selected periods.
        """
        total_created = 0
        total_skipped = 0

        for period in queryset:
            result = bulk_generate_payroll(period)
            total_created += result['created']
            total_skipped += result['skipped']

        self.message_user(
            request,
            f"Payroll generation completed. Created: {total_created}, Skipped: {total_skipped}",
            messages.SUCCESS
        )

    generate_payroll_for_period.short_description = "Generate payroll for selected periods"


# ==========================================================
# ALLOWANCES
# ==========================================================
@admin.register(Allowance)
class AllowanceAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_taxable', 'default_amount')
    search_fields = ('name',)  # <-- Required for autocomplete


@admin.register(EmployeeAllowance)
class EmployeeAllowanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'allowance', 'amount', 'period_month', 'period_year')
    list_filter = ('period_year', 'period_month', 'allowance')
    autocomplete_fields = ['employee', 'allowance']


# ==========================================================
# DEDUCTIONS
# ==========================================================
@admin.register(Deduction)
class DeductionAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_statutory', 'apply_rate', 'rate', 'default_amount')
    list_filter = ('is_statutory', 'apply_rate')
    search_fields = ('name',)  # <-- Required for autocomplete


@admin.register(EmployeeStatutoryDeduction)
class EmployeeStatutoryDeductionAdmin(admin.ModelAdmin):
    list_display = ('employee', 'deduction', 'amount', 'period_month', 'period_year')
    list_filter = ('period_year', 'period_month', 'deduction')
    autocomplete_fields = ['employee', 'deduction']


@admin.register(EmployeeNonStatutoryDeduction)
class EmployeeNonStatutoryDeductionAdmin(admin.ModelAdmin):
    list_display = ('employee', 'deduction', 'amount', 'period_month', 'period_year')
    list_filter = ('period_year', 'period_month', 'deduction')
    autocomplete_fields = ['employee', 'deduction']


# ==========================================================
# INCENTIVES
# ==========================================================
@admin.register(Incentive)
class IncentiveAdmin(admin.ModelAdmin):
    list_display = ('employee', 'name', 'amount', 'is_taxable', 'period_month', 'period_year')
    list_filter = ('period_year', 'period_month', 'is_taxable')
    autocomplete_fields = ['employee']
    search_fields = ('name',)  # Optional but useful for searching by incentive name


# ==========================================================
# OVERTIME
# ==========================================================
@admin.register(OvertimeRecord)
class OvertimeRecordAdmin(admin.ModelAdmin):
    list_display = ('employee', 'period_month', 'period_year', 
                    'standard_hours', 'night_hours', 'weekend_hours', 'status', 'total_amount')
    list_filter = ('period_year', 'period_month', 'status')
    autocomplete_fields = ['employee']


# ==========================================================
# EMPLOYEE PAYROLL
# ==========================================================
@admin.register(EmployeePayroll)
class EmployeePayrollAdmin(admin.ModelAdmin):
    list_display = ('employee', 'period', 'gross_pay', 'paye', 'total_deductions', 'net_pay', 'status', 'processed_at')
    list_filter = ('status', 'period__year', 'period__month')
    autocomplete_fields = ['employee', 'period']
    readonly_fields = ('gross_pay', 'paye', 'total_deductions', 'net_pay', 'processed_at')
    ordering = ('-period__year', '-period__month', 'employee')
