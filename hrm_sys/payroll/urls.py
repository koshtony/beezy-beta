from django.urls import path
from payroll.admin import bulk_generate_payroll_view

urlpatterns = [
    path('admin/payroll/employee-payroll/bulk-generate/', bulk_generate_payroll_view, name='payroll_bulk_generate'),
]
