from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    SignupView,
    LoginView,
    LogoutView,
    CurrentUserView,
    UserUpdateView,
    DepartmentViewSet,
    SubDepartmentViewSet,
    RoleViewSet,
    EmployeeViewSet,
)

# =====================================
# ROUTER for viewsets (auto CRUD)
# =====================================
router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"subdepartments", SubDepartmentViewSet, basename="subdepartment")
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"employees", EmployeeViewSet, basename="employee")
router	.register(r"profile", EmployeeViewSet, basename="my-profile")

# =====================================
# URL PATTERNS
# =====================================
urlpatterns = [
    # AUTHENTICATION
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # USER MANAGEMENT
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("update/", UserUpdateView.as_view(), name="user-update"),  # current user
    path("update/<int:pk>/", UserUpdateView.as_view(), name="user-update-admin"),  # admin editing any user

    # ROUTED VIEWSETS
    path("", include(router.urls)),
]

urlpatterns += router.urls