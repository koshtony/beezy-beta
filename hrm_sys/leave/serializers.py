from rest_framework import serializers
from .models import LeaveType, LeaveRequest, LeaveBalance, LeaveApprover,LeaveApprovalRecord


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = '__all__'


class LeaveBalanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)

    class Meta:
        model = LeaveBalance
        fields = [
            'id', 'employee', 'employee_name', 'leave_type', 'leave_type_name',
            'year', 'remaining_days', 'allocated_days', 'used_days'	
        ]


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'employee', 'employee_name', 'leave_type', 'leave_type_name',
            'start_date', 'end_date', 'day_type', 'total_days', 'reason',
            'attachment', 'attachment_url', 'status', 'approver', 'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'approver', 'created_at', 'updated_at']

    def get_attachment_url(self, obj):
        request = self.context.get('request')
        if obj.attachment and hasattr(obj.attachment, 'url'):
            return request.build_absolute_uri(obj.attachment.url)
        return None


class LeaveApproverSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    subdepartment_name = serializers.CharField(source='subdepartment.name', read_only=True)
    approver_name = serializers.CharField(source='approver.full_name', read_only=True)

    class Meta:
        model = LeaveApprover
        fields = [
            'id', 'department', 'department_name',
            'subdepartment', 'subdepartment_name',
            'approver', 'approver_name'
        ]


class LeaveApprovalRecordSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(source="approver.full_name", read_only=True)

    class Meta:
        model = LeaveApprovalRecord
        fields = ["id", "approver_name", "action", "remarks", "timestamp"]