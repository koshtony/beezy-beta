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
        image = request.data.get("image")  # optional
        ip_address = request.META.get('REMOTE_ADDR')

        if not latitude or not longitude:
            return Response({"error": "Latitude and Longitude required"}, status=400)

        # Assume employee has at least one station
        station = employee.stations.first()
        if not station:
            return Response({"error": "No station assigned"}, status=400)

        # Compute distance from station
        distance = calculate_distance(
            float(latitude), float(longitude),
            float(station.latitude), float(station.longitude)
        )

        # Within threshold (e.g. 100m)
        threshold = 100
        valid = distance <= threshold

        # Save record
        attendance = Attendance.objects.create(
            employee=employee,
            check_in_latitude=latitude,
            check_in_longitude=longitude,
            distance_from_station=distance,
            is_valid=valid,
            check_in_date=timezone.now(),
            device_ip=ip_address,
            #image=image if image else None,
        )
        
        attendance.save()

        return Response({
            "employee": employee.full_name,
            "station": station.name,
            "distance": round(distance, 2),
            "valid": valid,
            "message": "Clocked in successfully" if valid else "Invalid clock-in (too far)",
        }, status=200)