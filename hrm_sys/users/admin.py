from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Department, SubDepartment, Role, Employee
from leave.models import LeaveBalance


# ==============================
# CustomUser Admin
# ==============================
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_active", "is_staff", "is_superuser")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email")
    ordering = ("username",)

    # --- Use Django's built-in password handling ---
    fieldsets = (
        ("Account Info", {
            "fields": (
                ("username", "email"),  # side-by-side grid look
                ("role", "is_active", "is_staff", "is_superuser"),
                "password",
            )
        }),
    )

    # --- For 'Add user' page ---
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                ("username", "email"),
                ("role",),
                ("password1", "password2"),  # default Django password fields
                ("is_active", "is_staff"),
            ),
        }),
    )

class LeaveBalanceInline(admin.TabularInline):
    model = LeaveBalance
    extra = 1
    fields = ('leave_type', 'year','allocated_days', 'used_days', 'remaining_days')
    autocomplete_fields = ('leave_type',)
    verbose_name = "Leave Allocation"
    verbose_name_plural = "Leave Allocations"


# --- Extend Employee Admin ---
# Unregister the existing Employee admin if it's already registered
try:
    admin.site.unregister(Employee)
except admin.sites.NotRegistered:
    pass
# ==============================
# Employee Admin
# ==============================
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "employee_code",
        "get_full_name",
        "phone_number",
        "department",
        "sub_department",
        "job_position",
        "employment_type",
        "job_status",
        "created_at",
    )
    list_filter = ("department", "employment_type", "job_status")
    search_fields = ("employee_code", "full_name", "phone_number", "department__name")
    ordering = ("-created_at",)
    readonly_fields = ("employee_code", "created_at", "updated_at")

    fieldsets = (
        ("Personal Information", {
            "fields": (
                ("full_name", "phone_number"),
                ("gender", "marital_status"),
                ("date_of_birth", "national_id"),
                ("address",),
            ),
        }),
        ("Job Details", {
            "fields": (
                ("employee_code", "date_of_joining"),
                ("department", "sub_department"),
                ("job_position", "employment_type"),
                ("job_status","stations"),
            ),
        }),
        ("Next of Kin", {
            "fields": (
                ("next_of_kin_name", "next_of_kin_relationship"),
                ("next_of_kin_phone",),
            ),
        }),
        ("Documents", {
            "fields": ("documents","profile_image"),
        }),
        ("Timestamps", {
            "fields": (("created_at", "updated_at"),),
        }),
    )
    
    autocomplete_fields = ("stations",)
    
    inlines = [LeaveBalanceInline]

    # ✅ Add this method to avoid admin.E108
    def get_full_name(self, obj):
        return getattr(obj, "full_name", "—")
    get_full_name.short_description = "Full Name"


# ==============================
# Department Admin
# ==============================
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


# ==============================
# SubDepartment Admin
# ==============================
@admin.register(SubDepartment)
class SubDepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "description")
    search_fields = ("name", "department__name")


# ==============================
# Role Admin
# ==============================
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "hierarchy_level")
    search_fields = ("name",)
    ordering = ("hierarchy_level",)