from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta, time, datetime
from django.apps import apps
from math import radians, sin, cos, sqrt, atan2
from django.contrib.auth import get_user_model
from django.utils.timezone import is_naive, localtime


# -----------------------------
# Station model
# -----------------------------
class Station(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)

    # Keep variable names; align coordinate precision for consistency
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    location_pin = models.CharField(max_length=20, null=True, blank=True)

    # Business hours (defaults preserved)
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


# -----------------------------
# Utilities
# -----------------------------
def _to_float(val):
    """Safely cast Decimal/float/str to float for math ops."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters using Haversine formula."""
    # Preserve function name; add safe casting for Decimal/float inputs
    lat1 = _to_float(lat1)
    lon1 = _to_float(lon1)
    lat2 = _to_float(lat2)
    lon2 = _to_float(lon2)

    if None in [lat1, lon1, lat2, lon2]:
        return None

    R = 6371000  # Earth radius in meters
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


# -----------------------------
# Attendance model
# -----------------------------
class Attendance(models.Model):
    employee = models.ForeignKey(
        "users.Employee",
        on_delete=models.CASCADE,
        related_name="attendances",
    )

    # ✅ Check-In details (keep variable names; switch to Decimal for precision)
    check_in_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_in_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_in_image = models.ImageField(upload_to="attendance_photos/", null=True, blank=True)
    check_in_date = models.DateTimeField(null=True, blank=True)

    # ✅ Check-Out details
    check_out_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_out_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
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

    # -----------------------------
    # Validation orchestration
    # -----------------------------
    def validate_attendance(self):
        """
        Compute and set:
        - distance_from_station
        - is_valid
        - is_late_check_in
        - is_early_check_out
        - device_changed

        Resets flags safely if data is missing to avoid stale values.
        """
        Station = apps.get_model("attendance", "Station")
        employee_stations = getattr(self.employee, "stations", None)
        employee_stations_qs = employee_stations.all() if employee_stations else Station.objects.none()

        # Normalize timestamps to aware and localized datetimes
        def normalize_dt(dt):
            if dt is None:
                return None
            if is_naive(dt):
                dt = timezone.make_aware(dt)
            return localtime(dt)

        normalized_check_in = normalize_dt(self.check_in_date)
        normalized_check_out = normalize_dt(self.check_out_date)

        # Default resets to avoid stale flags
        self.distance_from_station = None
        self.is_valid = False
        self.is_late_check_in = False
        self.is_early_check_out = False

        # -----------------------------
        # Distance validation (nearest station)
        # -----------------------------
        min_distance = None
        nearest_station = None

        has_check_in_coords = (self.check_in_latitude is not None and self.check_in_longitude is not None)

        if has_check_in_coords and employee_stations_qs.exists():
            for station in employee_stations_qs:
                if station.latitude is not None and station.longitude is not None:
                    distance = calculate_distance(
                        self.check_in_latitude,
                        self.check_in_longitude,
                        station.latitude,
                        station.longitude,
                    )
                    if distance is None:
                        continue
                    if min_distance is None or distance < min_distance:
                        min_distance = distance
                        nearest_station = station

            self.distance_from_station = min_distance
            self.is_valid = (min_distance is not None and min_distance <= self.VALID_DISTANCE_THRESHOLD)

        # -----------------------------
        # Lateness check (check-in)
        # -----------------------------
        if nearest_station and nearest_station.check_in_time and normalized_check_in:
            # Compute station baseline at local date
            station_in_dt = timezone.make_aware(
                datetime.combine(normalized_check_in.date(), nearest_station.check_in_time),
                timezone.get_current_timezone()
            )
            station_in_dt = localtime(station_in_dt)
            late_threshold = station_in_dt + timedelta(minutes=self.LATE_THRESHOLD_MINUTES)
            self.is_late_check_in = normalized_check_in > late_threshold

        # -----------------------------
        # Earliness check (check-out)
        # -----------------------------
        if nearest_station and nearest_station.check_out_time and normalized_check_out:
            station_out_dt = timezone.make_aware(
                datetime.combine(normalized_check_out.date(), nearest_station.check_out_time),
                timezone.get_current_timezone()
            )
            station_out_dt = localtime(station_out_dt)
            early_threshold = station_out_dt - timedelta(minutes=self.EARLY_THRESHOLD_MINUTES)
            self.is_early_check_out = normalized_check_out < early_threshold

        # -----------------------------
        # Device/IP comparison
        # -----------------------------
        self.device_changed = False
        last_record = (
            Attendance.objects.filter(employee=self.employee)
            .exclude(pk=self.pk)
            .order_by("-created_at")
            .first()
        )
        if last_record and last_record.device_ip and self.device_ip:
            # Preserve previous_ip variable; populate for audit trail
            self.previous_ip = last_record.device_ip
            self.device_changed = (self.device_ip != last_record.device_ip)

    # -----------------------------
    # Save override
    # -----------------------------
    def save(self, *args, **kwargs):
        # Ensure validation runs before persisting
        self.validate_attendance()
        super().save(*args, **kwargs)