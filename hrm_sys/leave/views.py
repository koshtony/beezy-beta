from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import models
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import LeaveRequest, LeaveApprovalRecord, LeaveApprover
from .serializers import LeaveRequestSerializer, LeaveApprovalRecordSerializer
from users.models import Employee


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing leave requests.
    Supports: list, create, retrieve, approve, reject.
    """
    queryset = LeaveRequest.objects.select_related("employee", "leave_type").prefetch_related("approval_records")
    serializer_class = LeaveRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    # --------------------------------------------------
    # 1️⃣ Filter by logged-in user
    # --------------------------------------------------
    def get_queryset(self):
        user = self.request.user
        employee = Employee.objects.filter(employee_code=user.username).first()

        qs = self.queryset
        if self.action == "to_approve":
            return qs.filter(approval_records__approver=employee, approval_records__action="pending").distinct()
        if employee:
            return qs.filter(employee=employee)
        return qs.none()

    # --------------------------------------------------
    # 2️⃣ Create leave request
    # --------------------------------------------------
    def perform_create(self, serializer):
        user = self.request.user
        employee = Employee.objects.filter(employee_code=user.username).first()
        if not employee:
            raise Response({"error": "Employee profile not found for this user."}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(employee=employee)

    # --------------------------------------------------
    # 3️⃣ Approver view — pending approvals
    # --------------------------------------------------
    @action(detail=False, methods=["get"], url_path="to-approve")
    def to_approve(self, request):
        user = request.user
        employee = Employee.objects.filter(employee_code=user.username).first()
        if not employee:
            return Response({"detail": "Approver profile not found."}, status=status.HTTP_400_BAD_REQUEST)

        pending = LeaveRequest.objects.filter(
            approval_records__approver=employee,
            approval_records__action="pending"
        ).distinct()

        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)

    # --------------------------------------------------
    # 4️⃣ Approve leave
    # --------------------------------------------------
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        user = request.user
        employee = Employee.objects.filter(employee_code=user.username).first()
        leave_request = self.get_object()

        try:
            record = leave_request.approval_records.get(approver=employee, action="pending")
        except LeaveApprovalRecord.DoesNotExist:
            return Response({"detail": "No pending approval for this approver."},
                            status=status.HTTP_400_BAD_REQUEST)

        record.approve()
        return Response({"detail": "Leave approved successfully."}, status=status.HTTP_200_OK)
    @action(detail=False, methods=["get"], url_path="my_leaves")
    def my_leaves(self, request):
        """
        Returns leaves submitted by the logged-in employee
        """
        user = request.user
        employee = get_object_or_404(Employee, employee_code=user.username)
        leaves = LeaveRequest.objects.filter(employee=employee).order_by("-created_at")

        serializer = self.get_serializer(leaves, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    # --------------------------------------------------
    # 5️⃣ Reject leave
    # --------------------------------------------------
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        user = request.user
        employee = Employee.objects.filter(employee_code=user.username).first()
        remarks = request.data.get("remarks", "")
        leave_request = self.get_object()

        try:
            record = leave_request.approval_records.get(approver=employee, action="pending")
        except LeaveApprovalRecord.DoesNotExist:
            return Response({"detail": "No pending approval for this approver."},
                            status=status.HTTP_400_BAD_REQUEST)

        record.reject(remarks)
        return Response({"detail": "Leave rejected successfully."}, status=status.HTTP_200_OK)
