from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.apps import apps
from math import radians, sin, cos, sqrt, atan2
from django.contrib.auth import get_user_model
from datetime import time,datetime



class Station(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_pin = models.CharField(max_length=20, null=True, blank=True)
    
    check_in_time = models.TimeField(default=time(8, 0))   # 8:00 AM
    check_out_time = models.TimeField(default=time(17, 0)) # 5:00 PM

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_stations"
    )
    last_updated = models.DateTimeField(auto_now=True)
    

    def __str__(self):
        return self.name

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters using Haversine formula."""
    if None in [lat1, lon1, lat2, lon2]:
        return None
    R = 6371000  # Earth radius in meters
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c





class Attendance(models.Model):
    employee = models.ForeignKey(
        "users.Employee",
        on_delete=models.CASCADE,
        related_name="attendances",
    )
    # ✅ Check-In details
    check_in_latitude = models.FloatField(null=True, blank=True)
    check_in_longitude = models.FloatField(null=True, blank=True)
    check_in_image = models.ImageField(upload_to="attendance_photos/", null=True, blank=True)
    check_in_date = models.DateTimeField(null=True, blank=True)

    # ✅ Check-Out details
    check_out_latitude = models.FloatField(null=True, blank=True)
    check_out_longitude = models.FloatField(null=True, blank=True)
    check_out_image = models.ImageField(upload_to="attendance_photos/", null=True, blank=True)
    check_out_date = models.DateTimeField(null=True, blank=True)

    # ✅ Validation and metadata
    device_ip = models.GenericIPAddressField(null=True, blank=True)
    previous_ip = models.GenericIPAddressField(null=True, blank=True)
    distance_from_station = models.FloatField(null=True, blank=True)
    is_valid = models.BooleanField(default=False)
    is_late_check_in = models.BooleanField(default=False)
    is_early_check_out = models.BooleanField(default=False)
    device_changed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    VALID_DISTANCE_THRESHOLD = 100.0  # meters
    LATE_THRESHOLD_MINUTES = 10
    EARLY_THRESHOLD_MINUTES = 10

    class Meta:
        ordering = ["-check_in_date"]

    def __str__(self):
        return f"{self.employee} - {self.check_in_date.strftime('%Y-%m-%d %H:%M') if self.check_in_date else 'N/A'}"

    def save(self, *args, **kwargs):
        Station = apps.get_model("attendance", "Station")
        employee_stations = self.employee.stations.all()

        # ✅ Distance validation
        if self.check_in_latitude and self.check_in_longitude and employee_stations.exists():
            min_distance = None
            nearest_station = None

            for station in employee_stations:
                if station.latitude and station.longitude:
                    distance = calculate_distance(
                        self.check_in_latitude,
                        self.check_in_longitude,
                        station.latitude,
                        station.longitude,
                    )
                    if min_distance is None or distance < min_distance:
                        min_distance = distance
                        nearest_station = station

            self.distance_from_station = min_distance
            self.is_valid = (
                min_distance is not None and min_distance <= self.VALID_DISTANCE_THRESHOLD
            )

            # ✅ Time comparison (check-in lateness)
            if nearest_station and nearest_station.check_in_time and self.check_in_date:
                current_dt = self.check_in_date
                late_threshold = timezone.make_aware(
                    datetime.combine(current_dt.date(), nearest_station.check_in_time)
                ) + timedelta(minutes=self.LATE_THRESHOLD_MINUTES)

                self.is_late_check_in = current_dt > late_threshold


            # ✅ Time comparison (check-out earliness)
            if nearest_station and nearest_station.check_out_time and self.check_out_date:
                current_dt = self.check_out_date
                early_threshold = timezone.make_aware(
                    datetime.combine(current_dt.date(), nearest_station.check_out_time)
                ) - timedelta(minutes=self.EARLY_THRESHOLD_MINUTES)

                self.is_early_check_out = current_dt < early_threshold

        # ✅ Device/IP comparison
        last_record = (
            Attendance.objects.filter(employee=self.employee)
            .exclude(pk=self.pk)
            .order_by("-created_at")
            .first()
        )
        if last_record and last_record.device_ip and self.device_ip:
            self.device_changed = self.device_ip != last_record.device_ip

        super().save(*args, **kwargs)
