from django.contrib import admin
from django.utils.html import format_html
from .models import ApprovalType, ApprovalFlow, ApprovalRecord, Notification


# ----------------------------
# INLINE MODELS
# ----------------------------

class ApprovalFlowInline(admin.TabularInline):
    model = ApprovalFlow
    extra = 1
    autocomplete_fields = ["department", "sub_department", "role"]
    fields = (
        "level",
        "department",
        "sub_department",
        "role",
        "is_proper_approver",
        "notify_approver",
        "is_active",
    )
    ordering = ("level",)


class NotificationInline(admin.TabularInline):
    model = Notification
    extra = 0
    readonly_fields = ("recipient", "title", "message", "is_read", "created_at")
    can_delete = False


# ----------------------------
# APPROVAL TYPE ADMIN
# ----------------------------

@admin.register(ApprovalType)
class ApprovalTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)
    inlines = [ApprovalFlowInline]


# ----------------------------
# APPROVAL FLOW ADMIN
# ----------------------------

@admin.register(ApprovalFlow)
class ApprovalFlowAdmin(admin.ModelAdmin):
    list_display = (
        "approval_type",
        "level",
        "department",
        "sub_department",
        "role",
        "is_proper_approver",
        "notify_approver",
        "is_active",
    )
    list_filter = ("approval_type", "is_active", "is_proper_approver", "notify_approver")
    search_fields = (
        "approval_type__name",
        "department__name",
        "sub_department__name",
        "role__name",
    )
    ordering = ("approval_type", "level")


# ----------------------------
# APPROVAL RECORD ADMIN
# ----------------------------

@admin.register(ApprovalRecord)
class ApprovalRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "approval_type",
        "creator",
        "approver",
        "level",
        "colored_status",
        "created_at",
        "approved_at",
    )
    list_filter = ("approval_type", "status", "is_proper_approver")
    search_fields = (
        "creator__full_name",
        "approver__full_name",
        "approval_type__name",
        "content_type__model",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "approved_at",
    )
    inlines = [NotificationInline]
    ordering = ("-created_at",)

    def colored_status(self, obj):
        color_map = {
            "pending": "orange",
            "approved": "green",
            "rejected": "red",
            "notified": "blue",
        }
        color = color_map.get(obj.status, "black")
        return format_html(
            f'<b style="color:{color}; text-transform:capitalize;">{obj.status}</b>'
        )

    colored_status.short_description = "Status"

    def save_model(self, request, obj, form, change):
        """
        Auto-handle notification triggers and save logic already in model.
        """
        super().save_model(request, obj, form, change)
        if not change:
            print(
                f"🔔 New ApprovalRecord created: {obj.approval_type.name} by {obj.creator.full_name}"
            )
        else:
            print(
                f"🔔 ApprovalRecord #{obj.id} updated — current status: {obj.status.upper()}"
            )


# ----------------------------
# NOTIFICATION ADMIN
# ----------------------------

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "recipient",
        "title",
        "is_read",
        "created_at",
        "related_record_display",
    )
    list_filter = ("is_read", "created_at")
    search_fields = ("recipient__full_name", "title", "message")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    def related_record_display(self, obj):
        if obj.related_record:
            return format_html(
                f'<a href="/admin/{obj.related_record._meta.app_label}/{obj.related_record._meta.model_name}/{obj.related_record.id}/change/">{obj.related_record}</a>'
            )
        return "—"

    related_record_display.short_description = "Related Approval"
