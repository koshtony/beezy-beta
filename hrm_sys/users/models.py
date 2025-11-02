from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings
from attendance.models import Station
import uuid


# -------------------------------
# Custom User Model
# -------------------------------
class CustomUser(AbstractUser):
    USER_ROLE_CHOICES = [
        ('manager', 'Manager'),
        ('normal', 'Normal'),
        ('special', 'Special'),
    ]

    role = models.CharField(max_length=20, choices=USER_ROLE_CHOICES, default='normal')
    is_active = models.BooleanField(default=False)  # inactive until approved

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_manager(self):
        return self.role == 'manager'

    @property
    def is_special(self):
        return self.role == 'special'


# -------------------------------
# Employee Profile
# -------------------------------


User = settings.AUTH_USER_MODEL


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    def __str__(self): return self.name


class SubDepartment(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="sub_departments")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    class Meta:
        unique_together = ('department', 'name')
    def __str__(self): return f"{self.department.name} - {self.name}"


class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    hierarchy_level = models.PositiveIntegerField(help_text="Lower = higher rank (e.g. 1=CEO)")
    class Meta:
        ordering = ["hierarchy_level"]
    def __str__(self): return self.name


class Employee(models.Model):
    EMPLOYMENT_TYPE_CHOICES = [
        ('full_time', 'Full-Time'),
        ('part_time', 'Part-Time'),
        ('contract', 'Contract'),
        ('intern', 'Intern'),
    ]

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    MARITAL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
    ]

    JOB_STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
        ('resigned', 'Resigned'),
    ]

   

 
    employee_code = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=255, null=True)
    phone_number = models.CharField(max_length=20,null=True)
    date_of_joining = models.DateField(null=True, blank=True)
    
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    sub_department = models.ForeignKey(SubDepartment, on_delete=models.SET_NULL, null=True, blank=True)
    stations = models.ManyToManyField(
        "attendance.Station",
        related_name="employees",
        blank=True
    )
    
    job_position = models.CharField(max_length=255, blank=True, null=True)
    employment_type = models.CharField(max_length=50, choices=[("full_time", "Full Time"), ("part_time", "Part Time"), ("contract", "Contract")])
    gender = models.CharField(max_length=10,null=True, choices=[("male", "Male"), ("female", "Female"), ("other", "Other")])
    marital_status = models.CharField(max_length=15,null=True, choices=[("single", "Single"), ("married", "Married"), ("divorced", "Divorced")])
    job_status = models.CharField(max_length=20, choices=[("active", "Active"), ("inactive", "Inactive")])
    national_id = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    
    bank_account_number = models.CharField(max_length=30, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    
    next_of_kin_name = models.CharField(max_length=255, blank=True, null=True)
    next_of_kin_relationship = models.CharField(max_length=100, blank=True, null=True)
    next_of_kin_phone = models.CharField(max_length=20, blank=True, null=True)
    
    documents = models.FileField(upload_to="employee_docs/", blank=True, null=True)
    profile_image = models.ImageField(
        upload_to="employee_photos/",
        null=True,
        blank=True,
        help_text="Upload employee profile picture"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    


    def save(self, *args, **kwargs):
        if not self.employee_code:
            self.employee_code = f"EMP-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


