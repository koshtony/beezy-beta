from rest_framework import viewsets, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db.models import Q

from .models import (
    LeaveType,
    LeaveRequest,
    LeaveBalance,
    LeaveApprover,
    LeaveApprovalRecord,
)
from .serializers import (
    LeaveTypeSerializer,
    LeaveRequestSerializer,
    LeaveBalanceSerializer,
    LeaveApproverSerializer,
    LeaveApprovalRecordSerializer,
)
from users.models import Employee


class LeaveTypeViewSet(viewsets.ModelViewSet):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    permission_classes = [permissions.IsAuthenticated]


class LeaveRequestViewSet(viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.all().select_related(
        "employee", "leave_type", "department", "sub_department"
    )
    serializer_class = LeaveRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        employee = Employee.objects.filter(employee_code=user.username).first()
        if not employee:
            return LeaveRequest.objects.none()

        # Approver sees pending leave requests from their department/subdepartment
        if LeaveApprover.objects.filter(approver=employee).exists():
            return LeaveRequest.objects.filter(
                Q(status="pending"),
                Q(department=employee.department)
                | Q(sub_department=employee.sub_department)
            ).order_by("-created_at")

        # Employee sees their own leave requests
        return LeaveRequest.objects.filter(employee=employee).order_by("-created_at")

    def perform_create(self, serializer):
        employee = serializer.validated_data.get("employee")
        if not employee:
            raise serializers.ValidationError({"employee": "Employee is required"})

    
        if not Employee.objects.filter(id=employee.id).exists():
            raise serializers.ValidationError({"employee": "Invalid employee ID"})

        serializer.save()

    # ✅ View approval progress
    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        leave = self.get_object()
        records = LeaveApprovalRecord.objects.filter(leave_request=leave).select_related("approver")
        serializer = LeaveApprovalRecordSerializer(records, many=True)
        return Response(serializer.data)

    # ✅ Approve Leave
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        user = self.request.user
        approver = Employee.objects.filter(employee_code=user.username).first()
        if not approver:
            return Response({"detail": "Approver profile not found."}, status=status.HTTP_400_BAD_REQUEST)

        leave = self.get_object()
        try:
            leave.approve(approver)
        except Exception as e:
            return Response({"detail": f"Error Approving {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        LeaveApprovalRecord.objects.create(
            leave_request=leave,
            approver=approver,
            action="approved",
            timestamp=timezone.now(),
        )
        return Response({"detail": "Leave approved successfully."})

    # ✅ Reject Leave
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        user = self.request.user
        approver = Employee.objects.filter(employee_code=user.username).first()
        remarks = request.data.get("remarks", "")
        if not approver:
            return Response({"detail": "Approver profile not found."}, status=status.HTTP_400_BAD_REQUEST)

        leave = self.get_object()
        leave.status = "rejected"
        leave.save()

        LeaveApprovalRecord.objects.create(
            leave_request=leave,
            approver=approver,
            action="rejected",
            remarks=remarks,
            timestamp=timezone.now(),
        )
        return Response({"detail": "Leave rejected successfully."})

    # ✅ Employee’s own leaves
    @action(detail=False, methods=["get"])
    def my_leaves(self, request):
        user = self.request.user
        employee = Employee.objects.filter(employee_code=user.username).first()
        if not employee:
            return Response({"detail": "Employee profile not found."}, status=status.HTTP_400_BAD_REQUEST)

        leaves = LeaveRequest.objects.filter(
            employee=employee
            ).order_by("-created_at")
        serializer = self.get_serializer(leaves, many=True)
        return Response(serializer.data)

    # ✅ Approver’s pending approvals
    @action(detail=False, methods=["get"])
    def to_approve(self, request):
        user = self.request.user
        employee = Employee.objects.filter(employee_code=user.username).first()
        if not employee:
            return Response({"detail": "Approver profile not found."}, status=status.HTTP_400_BAD_REQUEST)

        pending = LeaveRequest.objects.filter(
            status="pending",
            approver = employee
        ).select_related("employee", "leave_type")

        serializer = self.get_serializer(pending, many=True)
        print(serializer.data)
        return Response(serializer.data)


class LeaveBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LeaveBalance.objects.all().select_related("employee", "leave_type")
    serializer_class = LeaveBalanceSerializer
    permission_classes = [permissions.IsAuthenticated]


class LeaveApproverViewSet(viewsets.ModelViewSet):
    queryset = LeaveApprover.objects.all().select_related("department", "sub_department", "approver")
    serializer_class = LeaveApproverSerializer
    permission_classes = [permissions.IsAuthenticated]
