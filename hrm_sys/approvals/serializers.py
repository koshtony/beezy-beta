from rest_framework import serializers
from .models import ApprovalType, ApprovalFlow, ApprovalRecord, Notification
from users.models import Employee


# --------------------------------------------
# EMPLOYEE (Lightweight Helper Serializer)
# --------------------------------------------
class EmployeeMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ["id", "full_name", "employee_code"]


# --------------------------------------------
# APPROVAL TYPE
# --------------------------------------------
class ApprovalTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalType
        fields = "__all__"


# --------------------------------------------
# APPROVAL FLOW
# --------------------------------------------
class ApprovalFlowSerializer(serializers.ModelSerializer):
    approval_type = ApprovalTypeSerializer(read_only=True)
    approver = EmployeeMiniSerializer(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    sub_department_name = serializers.CharField(source="sub_department.name", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = ApprovalFlow
        fields = [
            "id",
            "approval_type",
            "level",
            "approver",
            "department_name",
            "sub_department_name",
            "role_name",
            "is_proper_approver",
            "notify_approver",
            "is_active",
        ]


# --------------------------------------------
# APPROVAL RECORD
# --------------------------------------------
class ApprovalRecordSerializer(serializers.ModelSerializer):
    approval_type = ApprovalTypeSerializer(read_only=True)
    approver = EmployeeMiniSerializer(read_only=True)
    creator = EmployeeMiniSerializer(read_only=True)
    related_object = serializers.SerializerMethodField()
    document_url = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalRecord
        fields = [
            "id",
            "approval_type",
            "approver",
            "creator",
            "level",
            "status",
            "comment",
            "approved_at",
            "is_proper_approver",
            "was_notified",
            "created_at",
            "updated_at",
            "rich_content",
            "document_attachments",
            "document_url",
            "related_object",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "approved_at",
        ]

    def get_related_object(self, obj):
        """Show string representation of linked object (GenericForeignKey)"""
        return str(obj.content_object) if obj.content_object else None

    def get_document_url(self, obj):
        """Return full URL for attached document"""
        request = self.context.get("request")
        if obj.document_attachments and request:
            return request.build_absolute_uri(obj.document_attachments.url)
        return None


# --------------------------------------------
# NOTIFICATION
# --------------------------------------------
class NotificationSerializer(serializers.ModelSerializer):
    recipient = EmployeeMiniSerializer(read_only=True)
    approval_type = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    related_record_info = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "title",
            "message",
            "is_read",
            "created_at",
            "approval_type",
            "status",
            "related_record_id",
            "related_record_info",
        ]

    def get_approval_type(self, obj):
        if obj.related_record:
            return obj.related_record.approval_type.name
        return None

    def get_status(self, obj):
        if obj.related_record:
            return obj.related_record.status
        return None

    def get_related_record_info(self, obj):
        """Small summary for quick reference"""
        rec = obj.related_record
        if not rec:
            return None
        return {
            "id": rec.id,
            "approval_type": rec.approval_type.name,
            "status": rec.status,
            "creator": rec.creator.full_name,
            "approver": rec.approver.full_name,
            "level": rec.level,
        }
