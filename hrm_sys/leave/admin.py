from django.contrib import admin
from django.utils.html import format_html
from datetime import timedelta
from .models import (
    LeaveType,
    LeaveRequest,
    LeaveBalance,
    LeaveApprover,
    LeaveApprovalRecord,
)


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "total_days_per_year", "description")
    search_fields = ("name",)
    ordering = ("name",)


class LeaveApprovalRecordInline(admin.TabularInline):
    model = LeaveApprovalRecord
    extra = 0
    readonly_fields = ("approver", "action", "remarks", "timestamp")
    can_delete = False


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "leave_type",
        "start_date",
        "end_date",
        "days_requested",
        "status",
        "created_at",
        "approver",
    )
    list_filter = ("status", "leave_type", "start_date")
    search_fields = (
        "employee__full_name",
        "employee__employee_code",
        "leave_type__name",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "leave_summary",
        "days_requested",
    )
    inlines = [LeaveApprovalRecordInline]
    ordering = ("-created_at",)

    fieldsets = (
        ("Employee Info", {"fields": ("employee",)}),
        (
            "Leave Details",
            {
                "fields": (
                    "leave_type",
                    "start_date",
                    "end_date",
                    "day_type",
                    "reason",
                    "attachment",
                    "status",
                )
            },
        ),
        ("Leave Summary", {"fields": ("leave_summary", "days_requested")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def days_requested(self, obj):
        """Calculates total leave days requested."""
        if obj.day_type == 'half':
            return 0.5
        elif obj.start_date and obj.end_date:
            return (obj.end_date - obj.start_date).days + 1
        return 0

    days_requested.short_description = "Days Requested"

    def leave_summary(self, obj):
        """Shows current leave balance and remaining balance."""
        balance = LeaveBalance.objects.filter(
            employee=obj.employee, leave_type=obj.leave_type
        ).first()

        if not balance:
            return format_html("<b style='color:red;'>No leave balance record found.</b>")

        requested = self.days_requested(obj)
        total_days = balance.allocated_days
        remaining = balance.remaining_days
        used = balance.used_days
        new_balance = remaining - requested

        color = "green" if new_balance >= 0 else "red"

        return format_html(
            """
            <div style='padding:8px; border-radius:8px; background:orange;'>
                <b>Total Days:</b> {}<br>
                <b>Days Taken:</b> {}<br>
                <b>Remaining:</b> {}<br>
                <b>Days Requested:</b> {}<br>
                <b style='color:{};'>Balance After Approval:</b> {}
            </div>
            """,
            total_days,
            used,
            remaining,
            requested,
            color,
            remaining,
        )

    leave_summary.short_description = "Leave Summary"

@admin.register(LeaveApprover)
class LeaveApproverAdmin(admin.ModelAdmin):
    list_display = ('department', 'subdepartment', 'approver')
    list_filter = ('department', 'subdepartment')
    search_fields = (
        'department__name',
        'subdepartment__name',
        'approver__full_name',
    )
    ordering = ('department', 'subdepartment')