from django.shortcuts import render
from django.db.models import Q,F
from ..models import LeaveBalance, LeaveRequest, LeaveApprovalRecord
from users.models import Employee
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

def leave_balances_view(request):
    """Show leave balances and history depending on user role."""
    # Get logged-in employee record
    try:
        current_employee = Employee.objects.get(employee_code=request.user.username)
    except Employee.DoesNotExist:
        return render(request, "leave/leave_balances.html", {
            "balances": [],
            "history": [],
            "error": "No employee record found for your account."
        })

    query = request.GET.get("search", "")

    # ✅ If manager → show balances/records for their department
    if request.user.role == "manager":  # or current_employee.is_manager
        balances = LeaveBalance.objects.filter(
            employee__department=current_employee.department
        ).select_related("employee", "leave_type")

        history = LeaveRequest.objects.filter(
            employee__department=current_employee.department
        ).select_related("employee", "leave_type")

    # ✅ If not manager → show only their own balances/records
    else:
        balances = LeaveBalance.objects.filter(
            employee=current_employee
        ).select_related("employee", "leave_type")

        history = LeaveRequest.objects.filter(
            employee=current_employee
        ).select_related("employee", "leave_type")

    # ✅ Apply search filter if provided
    if query:
        balances = balances.filter(
            Q(employee__full_name__icontains=query) |
            Q(employee__employee_code__icontains=query) |
            Q(leave_type__name__icontains=query)
        )
        history = history.filter(
            Q(employee__full_name__icontains=query) |
            Q(employee__employee_code__icontains=query) |
            Q(leave_type__name__icontains=query)
        )

    balances = balances.order_by("employee__full_name", "leave_type__name")
    history = history.order_by("-created_at")

    context = {
        "balances": balances,
        "history": history,
        "search": query,
    }

    # ✅ HTMX partial rendering
    if request.headers.get("HX-Request") == "true" and not request.headers.get("HX-Boosted"):
        return render(request, "leave/partials/leave_balances_tables.html", context)

    return render(request, "leave/leave_balances.html", context)




@login_required
def pending_leaves_view(request):
    try:
        current_employee = Employee.objects.get(employee_code=request.user.username)
    except Employee.DoesNotExist:
        messages.error(request, "No employee record found.")
        return redirect("leave-balances")

    search = request.GET.get("search", "").strip()

    # Base queryset: only current step approvals for this employee
    pending_records = LeaveApprovalRecord.objects.filter(
        approver=current_employee,
        action="pending",
        step=F("leave_request__current_step")
    ).select_related("leave_request", "leave_request__employee", "leave_request__leave_type")

    if search:
        pending_records = pending_records.filter(
            Q(leave_request__employee__full_name__icontains=search) |
            Q(leave_request__leave_type__name__icontains=search) |
            Q(leave_request__reason__icontains=search)
        )

    leave_requests = []
    for rec in pending_records:
        lr = rec.leave_request
        try:
            lr.balance = LeaveBalance.objects.get(
                employee=lr.employee,
                leave_type=lr.leave_type,
                year=lr.year
            )
        except LeaveBalance.DoesNotExist:
            lr.balance = None
        leave_requests.append(lr)

    context = {
        "leave_requests": leave_requests,
        "search": search,
    }

    if request.headers.get("HX-Request") == "true":
        return render(request, "leave/partials/pending_leaves_list.html", context)

    return render(request, "leave/pending_leaves.html", context)


@login_required
def approve_leave_action(request, leave_id):
    try:
        current_employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        messages.error(request, "No employee record found.")
        return redirect("pending-approvals")

    leave = get_object_or_404(LeaveRequest, id=leave_id)

    # Get current step record
    current_record = leave.approval_records.filter(
        step=leave.current_step,
        approver=current_employee,
        action="pending"
    ).first()

    if not current_record:
        messages.error(request, "You are not authorized to approve this leave.")
        return redirect("pending-approvals")

    if request.method == "POST":
        action = request.POST.get("action")
        remarks = request.POST.get("remarks", "")
        if action == "approved":
            current_record.approve()
            messages.success(request, "Leave approved successfully.")
        elif action == "rejected":
            current_record.reject(remarks=remarks)
            messages.success(request, "Leave rejected.")
        return redirect("pending-approvals")

    return render(request, "leave/approve_leave.html", {
        "leave_request": leave,
        "current_record": current_record,
    })