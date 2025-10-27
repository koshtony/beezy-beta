from rest_framework import serializers
from .models import ApprovalRecord, ApprovalType, Notification


class ApprovalTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalType
        fields = "__all__"


class ApprovalRecordSerializer(serializers.ModelSerializer):
    approval_type = ApprovalTypeSerializer(read_only=True)
    approver_name = serializers.CharField(source="approver.full_name", read_only=True)
    creator_name = serializers.CharField(source="creator.full_name", read_only=True)
    related_object = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalRecord
        fields = [
            "id",
            "approval_type",
            "approver_name",
            "creator_name",
            "level",
            "status",
            "comment",
            "approved_at",
            "created_at",
            "is_proper_approver",
            "was_notified",
            "related_object",
        ]

    def get_related_object(self, obj):
        return str(obj.content_object)
    
class NotificationSerializer(serializers.ModelSerializer):
    approval_type = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id", "title", "message", "is_read", "created_at",
            "approval_type", "status", "related_record_id"
        ]

    def get_approval_type(self, obj):
        if obj.related_record:
            return obj.related_record.approval_type.name
        return None

    def get_status(self, obj):
        if obj.related_record:
            return obj.related_record.status
        return None
