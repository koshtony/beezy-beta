from rest_framework import viewsets, generics, permissions, status,filters
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password

from .models import Department, SubDepartment, Role, Employee, CustomUser
from .serializers import (
    UserSignupSerializer, UserLoginSerializer, UserDetailSerializer, UserUpdateSerializer,
    DepartmentSerializer, SubDepartmentSerializer, RoleSerializer, EmployeeSerializer,EmployeeProfileSerializer
)

User = get_user_model()


# ============================================================
# 🔹 AUTHENTICATION AND USER MANAGEMENT
# ============================================================

class SignupView(generics.CreateAPIView):
    """Handles user signup with password validation and admin approval"""
    serializer_class = UserSignupSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response({
            "message": "User created successfully. Please wait for admin approval.",
            "user": UserDetailSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    """Authenticate user and return JWT tokens"""
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # ✅ Try to find an employee whose employee_code matches username
        employee = Employee.objects.filter(employee_code=user.username).first()

        refresh = RefreshToken.for_user(user)

        # ✅ Build a clean response payload
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": employee.id if employee else None,        # <-- this is what Flutter needs
                "employee_code": employee.employee_code if employee else user.username,
                "first_name": getattr(employee, "first_name", user.first_name),
                "last_name": getattr(employee, "last_name", user.last_name),
                "email": user.email,
            },
        }, status=status.HTTP_200_OK)


class LogoutView(generics.GenericAPIView):
    """Blacklist the refresh token (logout)"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"error": "Refresh token is required."}, status=400)
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully."}, status=200)
        except Exception:
            return Response({"error": "Invalid or expired token."}, status=400)


class CurrentUserView(generics.RetrieveAPIView):
    """Return details of the current authenticated user"""
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserUpdateView(generics.UpdateAPIView):
    """Allow user to update profile (email only) or admin to update all"""
    queryset = CustomUser.objects.all()
    serializer_class = UserUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Allow users to update themselves or admin to update anyone
        user = self.request.user
        if user.is_staff and "pk" in self.kwargs:
            return CustomUser.objects.get(pk=self.kwargs["pk"])
        return user


# ============================================================
# 🔹 DEPARTMENT, ROLE & EMPLOYEE MANAGEMENT
# ============================================================

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]


class SubDepartmentViewSet(viewsets.ModelViewSet):
    queryset = SubDepartment.objects.select_related("department").all()
    serializer_class = SubDepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related("department", "sub_department").all()
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'employee_code',
        'first_name',
        'last_name',
        'phone_number',
        'department__name',
        'sub_department__name',
        'stations__name',
    ]
    ordering_fields = ['employee_code', 'first_name', 'last_name', 'phone_number']
    ordering = ['employee_code']


class MyProfileView(generics.RetrieveAPIView):
    """Return the logged-in user's employee profile"""
    serializer_class = EmployeeProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        try:
            return Employee.objects.get(employee_code=self.request.user.username)
        except Employee.DoesNotExist:
            return None

    def get(self, request, *args, **kwargs):
        employee = self.get_object()
        if not employee:
            return Response({"error": "Employee profile not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(employee, context={"request": request})
        return Response(serializer.data)