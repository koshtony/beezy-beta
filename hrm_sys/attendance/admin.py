from django.contrib import admin
from .models import Station,Attendance

@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = (
        "name", 
        "address", 
        "latitude", 
        "longitude", 
        "location_pin", 
        "updated_by", 
        "last_updated"
    )
    search_fields = ("name", "address")
    readonly_fields = ("last_updated",)
    
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        'employee__full_name', 
        'device_ip',
        'check_in_date', 
        'created_at',
        'distance_from_station',
        'is_valid',
    )
    list_filter = ('created_at',)
    search_fields = ('employee__full_name', 'employee__employee_code')
    ordering = ('-created_at',)
