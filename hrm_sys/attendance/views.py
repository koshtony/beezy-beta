from rest_framework import viewsets, permissions, filters
from .models import Station,Attendance
from .serializers import StationSerializer,AttendanceSerializer

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

