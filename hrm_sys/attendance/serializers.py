from rest_framework import serializers
from .models import Station,Attendance
from users.models import Employee
from math import radians, sin, cos, sqrt, atan2

class StationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = ['id', 'name', 'address', 'latitude', 'longitude', 'location_pin', 'last_updated', 'updated_by']


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    distance_meters = serializers.FloatField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id",
            "employee",
            "employee_name",
            "check_in_latitude",
            "check_in_longitude",
            "station_latitude",
            "station_longitude",
            "distance_meters",
            "is_valid",
            "check_in_date",
            "check_in_image",
            "device_ip",
        ]
        read_only_fields = ["distance_meters", "is_valid", "check_in_date"]

    def validate(self, data):
        """Ensure valid station coordinates before calculating distance"""
        if not all([
            data.get("check_in_latitude"),
            data.get("check_in_longitude"),
            data.get("station_latitude"),
            data.get("station_longitude"),
        ]):
            raise serializers.ValidationError("All latitude and longitude fields are required.")
        return data

    def create(self, validated_data):
        """Compute distance and validity before saving"""
        check_in_lat = validated_data["check_in_latitude"]
        check_in_lon = validated_data["check_in_longitude"]
        station_lat = validated_data["station_latitude"]
        station_lon = validated_data["station_longitude"]

        distance = self._calculate_distance(
            check_in_lat, check_in_lon, station_lat, station_lon
        )

        threshold = 100  # meters
        is_valid = distance <= threshold

        attendance = Attendance.objects.create(
            **validated_data,
            distance_meters=distance,
            is_valid=is_valid,
        )

        # Add message for response context
        self.context["message"] = (
            "Check-in successful." if is_valid
            else f"Check-in invalid: Distance ({distance:.2f} m) exceeds allowed threshold."
        )

        return attendance

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance using Haversine formula"""
        R = 6371000  # radius of Earth in meters
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    def to_representation(self, instance):
        """Add friendly message in API response"""
        rep = super().to_representation(instance)
        rep["message"] = self.context.get("message", "")
        return rep
