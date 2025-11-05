from rest_framework import serializers
from .models import LeaveType, LeaveBalance, LeaveApprover, LeaveRequest, LeaveApprovalRecord
from users.models import Employee


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = "__all__"


class LeaveBalanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)

    class Meta:
        model = LeaveBalance
        fields = [
            "id", "employee", "employee_name", "leave_type", "leave_type_name",
            "year", "allocated_days", "used_days", "remaining_days"
        ]


class LeaveApproverSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(source="approver.full_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    subdepartment_name = serializers.CharField(source="subdepartment.name", read_only=True)

    class Meta:
        model = LeaveApprover
        fields = [
            "id", "department", "department_name", "subdepartment", "subdepartment_name",
            "approver", "approver_name", "step"
        ]


class LeaveApprovalRecordSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(source="approver.full_name", read_only=True)

    class Meta:
        model = LeaveApprovalRecord
        fields = [
            "id", "approver", "approver_name", "step", "action", "remarks", "timestamp"
        ]


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    approval_records = LeaveApprovalRecordSerializer(many=True, read_only=True)
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = [
            "id", "employee", "employee_name",
            "leave_type", "leave_type_name",
            "start_date", "end_date", "reason", "total_days",
            "status", "current_step",
            "attachment", "attachment_url",
            "created_at", "updated_at",
            "approval_records"
        ]
        read_only_fields = ["status", "total_days", "current_step", "created_at", "updated_at"]

    def get_attachment_url(self, obj):
        """Return full attachment URL"""
        request = self.context.get("request")
        if obj.attachment and request:
            return request.build_absolute_uri(obj.attachment.url)
        elif obj.attachment:
            return obj.attachment.url
        return None

    def validate(self, attrs):
        """Ensure start < end"""
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and start > end:
            raise serializers.ValidationError("Start date cannot be after end date.")
        return attrs

    def create(self, validated_data):
        """Auto-detect employee and approvers"""
        request = self.context.get("request")
        user = request.user

        # Match logged in user to employee
        employee = Employee.objects.filter(employee_code=user.username).first()
        if not employee:
            raise serializers.ValidationError({"employee": "No matching employee profile found."})

        validated_data["employee"] = employee
        leave_request = LeaveRequest.objects.create(**validated_data)

        return leave_request
