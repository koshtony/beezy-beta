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
    show_change_link = True
    verbose_name_plural = "Generated Notifications"


# ----------------------------
# APPROVAL TYPE ADMIN
# ----------------------------

@admin.register(ApprovalType)
class ApprovalTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "flow_count")
    search_fields = ("name",)
    inlines = [ApprovalFlowInline]

    def flow_count(self, obj):
        return obj.flows.count()
    flow_count.short_description = "Approval Levels"


# ----------------------------
# APPROVAL FLOW ADMIN
# ----------------------------

@admin.register(ApprovalFlow)
class ApprovalFlowAdmin(admin.ModelAdmin):
    list_display = (
        "approval_type",
        "level",
        "approver",
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
    autocomplete_fields = ("approver","department", "sub_department", "role")


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
    list_filter = (
        "approval_type",
        "status",
        "is_proper_approver",
        "was_notified",
        "created_at",
    )
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
        "preview_rich_content",

    )
    inlines = [NotificationInline]
    ordering = ("-created_at",)
    autocomplete_fields = ("approver", "creator")

    fieldsets = (
        (None, {
            "fields": (
                "approval_type",
                "creator",
                "approver",
                "content_type",
                "object_id",
                "level",
                "status",
                "comment",
                "is_proper_approver",
                "was_notified",
            ),
        }),
        ("Rich Content & Attachments", {
            "classes": ("collapse",),
            "fields": ("rich_content",  "preview_rich_content"),
        }),
        ("Timestamps", {
            "classes": ("collapse",),
            "fields": ("created_at", "updated_at", "approved_at"),
        }),
    )

    # ---- Custom Display Helpers ----

    def colored_status(self, obj):
        color_map = {
            "pending": "orange",
            "approved": "green",
            "rejected": "red",
            "notified": "blue",
        }
        color = color_map.get(obj.status, "black")
        return format_html(f'<b style="color:{color}; text-transform:capitalize;">{obj.status}</b>')
    colored_status.short_description = "Status"

   

    def preview_rich_content(self, obj):
        if obj.rich_content:
            return format_html(f'<div style="max-width:500px;">{obj.rich_content}</div>')
        return "—"
    preview_rich_content.short_description = "Rich Content Preview"

 

    def save_model(self, request, obj, form, change):
        """
        Auto-handle notification triggers (logic already in model.save()).
        """
        super().save_model(request, obj, form, change)
        if not change:
            self.message_user(request, f"New approval record created: {obj.approval_type.name}")
        else:
            self.message_user(request, f"Approval record #{obj.id} updated (status: {obj.status})")


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
    list_filter = ("is_read", "created_at", "recipient")
    search_fields = ("recipient__full_name", "title", "message")
    readonly_fields = ("created_at", "related_record_link")
    ordering = ("-created_at",)

    def related_record_display(self, obj):
        if obj.related_record:
            return format_html(
                f'<a href="/admin/{obj.related_record._meta.app_label}/'
                f'{obj.related_record._meta.model_name}/{obj.related_record.id}/change/">'
                f'{obj.related_record}</a>'
            )
        return "—"
    related_record_display.short_description = "Related Approval"

    def related_record_link(self, obj):
        return self.related_record_display(obj)
    related_record_link.short_description = "Linked Approval Record"
