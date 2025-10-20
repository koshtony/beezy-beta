from django.db import models
from django.conf import settings
from django.utils import timezone
from django.apps import apps
from math import radians, sin, cos, sqrt, atan2
from django.contrib.auth import get_user_model



class Station(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_pin = models.CharField(max_length=20, null=True, blank=True)
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
    check_in_latitude = models.FloatField()
    check_in_longitude = models.FloatField()
    check_in_image = models.ImageField(upload_to="attendance_photos/", null=True, blank=True)
    check_in_date = models.DateTimeField(default=timezone.now)
    device_ip = models.GenericIPAddressField(null=True, blank=True)
    distance_from_station = models.FloatField(null=True, blank=True, help_text="Distance in meters")
    is_valid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    VALID_DISTANCE_THRESHOLD = 100.0  # meters

    class Meta:
        ordering = ["-check_in_date"]

    def __str__(self):
        return f"{self.employee} - {self.check_in_date.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        # Dynamically load Station model to avoid circular imports
        Station = apps.get_model("attendance", "Station")

        # Get employee’s assigned stations
        employee_stations = self.employee.stations.all()

        # Check distance to all stations, pick the nearest one
        min_distance = None
        for station in employee_stations:
            distance = calculate_distance(
                self.check_in_latitude,
                self.check_in_longitude,
                station.latitude,
                station.longitude,
            )
            if min_distance is None or distance < min_distance:
                min_distance = distance

        self.distance_from_station = min_distance
        self.is_valid = (
            min_distance is not None and min_distance <= self.VALID_DISTANCE_THRESHOLD
        )

        super().save(*args, **kwargs)


