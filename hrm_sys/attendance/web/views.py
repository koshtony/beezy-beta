from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models import Q
from django.utils import timezone
import datetime

from attendance.models import Attendance
from users.models import Employee


def get_employee_for_user(user):
    """
    Helper: fetch Employee record by matching employee_code with user.username.
    Returns None if not found.
    """
    try:
        return Employee.objects.get(employee_code=user.username)
    except Employee.DoesNotExist:
        return None



@login_required
def attendance_list(request):
    user = request.user
    employee = get_employee_for_user(user)

    # Role-aware queryset
    if user.is_manager and employee and employee.department:
        qs = Attendance.objects.filter(employee__department=employee.department)
    elif employee:
        qs = Attendance.objects.filter(employee=employee)
    else:
        qs = Attendance.objects.none()

    # ✅ Search filter
    search_query = request.GET.get("search")
    if search_query:
        qs = qs.filter(
            Q(employee__full_name__icontains=search_query) |
            Q(employee__employee_code__icontains=search_query) |
            Q(check_in_date__date__icontains=search_query)
        )

    # ✅ HTMX partial swap
    if request.headers.get("HX-Request") == "true" and not request.headers.get("HX-Boosted"):
        return render(request, "attendance/partials/attendance_table.html", {"attendances": qs})

    return render(request, "attendance/attendance_list.html", {"attendances": qs})


# -----------------------------
# Late Attendance Filter (role-aware)
# -----------------------------
@login_required
def late_attendance(request):
    user = request.user
    employee = get_employee_for_user(user)

    if user.is_manager and employee and employee.department:
        attendances = Attendance.objects.filter(
            employee__department=employee.department,
            is_late_check_in=True
        ).select_related("employee")
    elif employee:
        attendances = Attendance.objects.filter(
            employee=employee,
            is_late_check_in=True
        ).select_related("employee")
    else:
        attendances = Attendance.objects.none()

    return render(request, "attendance/late_attendance.html", {"attendances": attendances})


# -----------------------------
# Attendance History (role-aware)
# -----------------------------
@login_required
def attendance_history(request, employee_id=None):
    user = request.user
    employee = get_employee_for_user(user)

    if user.is_manager and employee and employee.department and employee_id:
        # Manager can view history of any employee in their department
        target_employee = get_object_or_404(Employee, pk=employee_id, department=employee.department)
    else:
        # Normal user → only own history
        target_employee = employee

    history = Attendance.objects.filter(employee=target_employee).order_by("-check_in_date")
    return render(request, "attendance/attendance_history.html", {
        "employee": target_employee,
        "history": history,
    })


# -----------------------------
# Dashboard (role-aware)
# -----------------------------


@login_required
def attendance_dashboard(request):
    user = request.user
    employee = get_employee_for_user(user)

    # Role-aware queryset
    if user.is_manager and employee and employee.department:
        qs = Attendance.objects.filter(employee__department=employee.department)
    elif employee:
        qs = Attendance.objects.filter(employee=employee)
    else:
        qs = Attendance.objects.none()

    # 🔍 Search filter
    search_query = request.GET.get("search")
    if search_query:
        qs = qs.filter(
            Q(employee__full_name__icontains=search_query) |
            Q(employee__employee_code__icontains=search_query)
        )

    # 📅 Period toggle
    toggle = request.GET.get("period", "all")
    now = timezone.now()

    if toggle == "year":
        qs = qs.filter(check_in_date__year=now.year)
    elif toggle == "month":
        qs = qs.filter(check_in_date__year=now.year, check_in_date__month=now.month)
    elif toggle == "week":
        start_week = now - datetime.timedelta(days=now.weekday())
        end_week = start_week + datetime.timedelta(days=7)
        qs = qs.filter(check_in_date__date__gte=start_week.date(),
                       check_in_date__date__lt=end_week.date())

    qs = qs.order_by("-check_in_date")

    # Summary counts
    total_count = qs.count()
    late_count = qs.filter(is_late_check_in=True).count()
    early_count = qs.filter(is_early_check_out=True).count()
    valid_count = qs.filter(is_valid=True).count()

    context = {
        "attendances": qs,
        "is_manager": user.is_manager,
        "total_count": total_count,
        "late_count": late_count,
        "early_count": early_count,
        "valid_count": valid_count,
        "toggle": toggle,
    }

    if request.headers.get("HX-Request") == "true" and not request.headers.get("HX-Boosted"):
        
        return render(request, "attendance/partials/attendance_dashboard_content.html", context)

    return render(request, "attendance/attendance_dashboard.html", context)