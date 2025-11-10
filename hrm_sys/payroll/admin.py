from django.contrib import admin
from django.utils.html import format_html
from .models import (
    PayrollSetting,
    PayrollPeriod,
    Allowance,
    Deduction,
    OvertimeRecord,
    EmployeePayroll,
    EmployeeAllowance,
    EmployeeDeduction,
)
from django.contrib import messages


# ==========================================================
#  INLINE MODELS
# ==========================================================
class EmployeeAllowanceInline(admin.TabularInline):
    model = EmployeeAllowance
    extra = 1


class EmployeeDeductionInline(admin.TabularInline):
    model = EmployeeDeduction
    extra = 1


# ==========================================================
#  PAYROLL SETTINGS ADMIN
# ==========================================================
@admin.register(PayrollSetting)
class PayrollSettingAdmin(admin.ModelAdmin):
    list_display = (
        "paye_band_1_limit",
        "paye_band_2_limit",
        "nssf_rate",
        "shif_rate",
        "housing_levy_rate",
        "overtime_hourly_rate",
        "updated_at",
    )
    readonly_fields = ("updated_at",)


# ==========================================================
#  PAYROLL PERIOD ADMIN
# ==========================================================
@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ("month", "year", "is_locked", "date_created")
    list_filter = ("is_locked", "year", "month")
    search_fields = ("year",)
    ordering = ("-year", "-month")


# ==========================================================
#  ALLOWANCE & DEDUCTION ADMIN
# ==========================================================
@admin.register(Allowance)
class AllowanceAdmin(admin.ModelAdmin):
    list_display = ("name", "is_taxable")
    list_filter = ("is_taxable",)
    search_fields = ("name",)


@admin.register(Deduction)
class DeductionAdmin(admin.ModelAdmin):
    list_display = ("name", "is_statutory")
    list_filter = ("is_statutory",)
    search_fields = ("name",)


# ==========================================================
#  OVERTIME ADMIN
# ==========================================================
@admin.register(OvertimeRecord)
class OvertimeRecordAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "period",
        "hours_worked",
        "hourly_rate",
        "total_amount_display",
        "approval_status",
    )
    list_filter = ("period__year", "period__month",)
    search_fields = ("employee__first_name", "employee__last_name", "employee__employee_code")

    def total_amount_display(self, obj):
        return f"{obj.total_amount:,.2f}"
    total_amount_display.short_description = "Total Amount"

    def approval_status(self, obj):
        """Dynamically show approval status (pending, approved, rejected)."""
        from approvals.models import ApprovalRecord
        record = ApprovalRecord.objects.filter(
            object_id=obj.id,
            content_type__model="overtimerecord"
        ).order_by("-created_at").first()
        if record:
            return record.status.title()
        return "Draft"
    approval_status.short_description = "Approval Status"

    actions = ["submit_for_approval"]

    def submit_for_approval(self, request, queryset):
        """Admin action: Submit overtime records for approval."""
        submitted = 0
        for overtime in queryset:
            overtime.submit_for_approval(creator=request.user.employee)
            submitted += 1
        self.message_user(request, f"{submitted} overtime record(s) submitted for approval.")
    submit_for_approval.short_description = "Submit selected for Approval"



# ==========================================================
#  EMPLOYEE PAYROLL ADMIN
# ==========================================================
@admin.register(EmployeePayroll)
class EmployeePayrollAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "period",
        "basic_salary_display",
        "gross_pay_display",
        "paye_display",
        "shif_display",
        "housing_levy_display",
        "net_pay_display",
        "status_colored",
        "processed_at",
    )
    list_filter = ("status", "period__year", "period__month")
    search_fields = ("employee__first_name", "employee__last_name", "employee__employee_code")
    inlines = [EmployeeAllowanceInline, EmployeeDeductionInline]
    readonly_fields = (
        "gross_pay",
        "paye",
        "shif",
        "nssf",
        "housing_levy",
        "net_pay",
        "processed_at",
    )
    actions = ["submit_for_approval_action"]

    # ----------------------------------------------------------
    #  DISPLAY HELPERS (formatted with commas & bold colors)
    # ----------------------------------------------------------
    def basic_salary_display(self, obj):
        return f"{obj.basic_salary:,.2f}"
    basic_salary_display.short_description = "Basic Salary"

    def gross_pay_display(self, obj):
        return f"{obj.gross_pay:,.2f}"
    gross_pay_display.short_description = "Gross Pay"

    def paye_display(self, obj):
        return f"{obj.paye:,.2f}"
    paye_display.short_description = "PAYE"

    def shif_display(self, obj):
        return f"{obj.shif:,.2f}"
    shif_display.short_description = "SHIF"

    def housing_levy_display(self, obj):
        return f"{obj.housing_levy:,.2f}"
    housing_levy_display.short_description = "Housing Levy"

    def net_pay_display(self, obj):
        return f"{obj.net_pay:,.2f}"
    net_pay_display.short_description = "Net Pay"

    def status_colored(self, obj):
        color = {
            "draft": "#6c757d",
            "pending_approval": "#ffc107",
            "approved": "#28a745",
            "rejected": "#dc3545",
        }.get(obj.status, "#6c757d")
        return format_html(f"<b><span style='color:{color}'>{obj.get_status_display()}</span></b>")
    status_colored.short_description = "Status"

    # ----------------------------------------------------------
    #  SAVE & ACTIONS
    # ----------------------------------------------------------
    def save_model(self, request, obj, form, change):
        """Automatically recalculate totals when saving."""
        obj.calculate_totals()
        super().save_model(request, obj, form, change)

    def submit_for_approval_action(self, request, queryset):
        """Admin action: Submit selected payrolls for approval."""
        submitted = 0
        for payroll in queryset:
            if payroll.status == "draft":
                payroll.submit_for_approval(creator=request.user.employee)
                submitted += 1
        messages.success(request, f"{submitted} payroll record(s) submitted for approval.")
    submit_for_approval_action.short_description = "Submit selected for Approval"
