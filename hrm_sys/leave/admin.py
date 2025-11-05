from django.contrib import admin
from .models import (
    LeaveType,
    LeaveBalance,
    LeaveApprover,
    LeaveRequest,
    LeaveApprovalRecord,
)

# -------------------------------
# Inline: Show approval records inside LeaveRequest admin
# -------------------------------
class LeaveApprovalRecordInline(admin.TabularInline):
    model = LeaveApprovalRecord
    extra = 0
    readonly_fields = ('approver', 'step', 'action', 'remarks', 'timestamp')
    can_delete = False


# -------------------------------
# LeaveRequest Admin
# -------------------------------
@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "leave_type",
        "start_date",
        "end_date",
        "total_days",
        "status",
        "current_step",
    )
    list_filter = ("status", "leave_type", "employee__department", "employee__sub_department")
    search_fields = ("employee__full_name", "leave_type__name")
    inlines = [LeaveApprovalRecordInline]
    readonly_fields = ("total_days", "created_at", "updated_at")

    fieldsets = (
        (None, {
            "fields": (
                "employee",
                "leave_type",
                "start_date",
                "end_date",
                "reason",
                "attachment",
                "total_days",
                "status",
                "current_step",
            )
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )


# -------------------------------
# LeaveType Admin
# -------------------------------
@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "total_days_per_year")
    search_fields = ("name",)


# -------------------------------
# LeaveBalance Admin
# -------------------------------
@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "year", "allocated_days", "used_days", "remaining_days")
    list_filter = ("year", "leave_type")
    search_fields = ("employee__full_name",)
    readonly_fields = ("remaining_days",)


# -------------------------------
# LeaveApprover Admin
# -------------------------------
@admin.register(LeaveApprover)
class LeaveApproverAdmin(admin.ModelAdmin):
    list_display = ("approver", "department", "subdepartment", "step")
    list_filter = ("department", "subdepartment")
    search_fields = ("approver__full_name",)


# -------------------------------
# LeaveApprovalRecord Admin (Standalone view)
# -------------------------------
@admin.register(LeaveApprovalRecord)
class LeaveApprovalRecordAdmin(admin.ModelAdmin):
    list_display = ("leave_request", "approver", "step", "action", "timestamp")
    list_filter = ("action", "step")
    search_fields = ("leave_request__employee__full_name", "approver__full_name")
    readonly_fields = ("leave_request", "approver", "step", "action", "remarks", "timestamp")
