from rest_framework import viewsets, permissions, filters,views
from .models import Station,Attendance
from users.models import Employee
from .serializers import StationSerializer,AttendanceSerializer
from math import radians, sin, cos, sqrt, atan2
from django.utils import timezone


class StationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing stations.
    Includes full CRUD + search + ordering.
    """
    queryset = Station.objects.all().order_by('name')
    serializer_class = StationSerializer
    permission_classes = [permissions.IsAuthenticated]

    # 🔍 Add search and ordering support
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'address', 'location_pin']
    ordering_fields = ['name', 'last_updated']
    ordering = ['name']

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
        

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attendance = serializer.save()

        if not attendance.is_valid:
            return Response({
                "message": (
                    f"Check-in location is invalid. "
                    f"Distance ({attendance.distance_meters:.2f} m) exceeds allowed threshold."
                ),
                "distance": attendance.distance_meters,
                "valid": attendance.is_valid
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": "Check-in successful.",
            "distance": attendance.distance_meters,
            "valid": attendance.is_valid
        }, status=status.HTTP_201_CREATED)


def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


class AttendanceClockView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        try:
            employee = Employee.objects.get(employee_code=user.username)
        except Employee.DoesNotExist:
            return Response({"error": "Employee not found"}, status=404)

        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")
        action = request.data.get("action", "check_in")
        ip_address = request.data.get("device_ip")
        image = request.FILES.get("image")

        if not latitude or not longitude:
            return Response({"error": "Latitude and longitude required"}, status=400)

        today_record = Attendance.objects.filter(
            employee=employee,
            check_in_date__date=timezone.now().date()
        ).first()

        # ✅ Handle Check-Out
        if action == "check_out" or (today_record and not today_record.check_out_date):
            if not today_record:
                return Response({"error": "No active check-in found"}, status=404)

            today_record.check_out_latitude = latitude
            today_record.check_out_longitude = longitude
            today_record.check_out_image = image
            today_record.check_out_date = timezone.now()
            today_record.device_ip = ip_address
            today_record.save()

            return Response({
                "message": "✅ Checked out successfully",
                "early_checkout": today_record.is_early_check_out,
                "device_changed": today_record.device_changed,
            })

        # ✅ Handle Check-In
        attendance = Attendance(
            employee=employee,
            check_in_latitude=latitude,
            check_in_longitude=longitude,
            check_in_date=timezone.now(),
            device_ip=ip_address,
        )
        if image:
            attendance.check_in_image = image
        attendance.save()

        return Response({
            "message": "✅ Checked in successfully",
            "late_check_in": attendance.is_late_check_in,
            "device_changed": attendance.device_changed,
        })