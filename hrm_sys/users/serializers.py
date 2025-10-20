from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import CustomUser
from .models import Department, SubDepartment, Employee,Role


User = get_user_model()

# ============================================
# USER SERIALIZERS
# ============================================

class UserSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = CustomUser
        fields = ["id", "username", "email", "password", "password2", "role"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        user = CustomUser.objects.create(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            role=validated_data.get("role", "normal"),
            is_active=False,  # must be approved by admin
        )
        user.set_password(validated_data["password"])
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data["username"], password=data["password"])
        if not user:
            raise serializers.ValidationError({"error": "Invalid username or password."})
        if not user.is_active:
            raise serializers.ValidationError({"error": "Account not yet approved by admin."})
        data["user"] = user
        return data


class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "username", "email", "role", "is_active", "date_joined"]


class UserUpdateSerializer(serializers.ModelSerializer):
    """For admin or self-profile update"""
    class Meta:
        model = CustomUser
        fields = ["email", "role", "is_active"]
        read_only_fields = ["role", "is_active"]  # Normal users can't change these

    def update(self, instance, validated_data):
        instance.email = validated_data.get("email", instance.email)
        # Only admins can toggle role or activation
        request = self.context.get("request")
        if request and request.user.is_staff:
            instance.role = validated_data.get("role", instance.role)
            instance.is_active = validated_data.get("is_active", instance.is_active)
        instance.save()
        return instance

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=True)
    role = serializers.ChoiceField(
        choices=[("manager", "Manager"), ("normal", "Normal"), ("special", "Special")],
        required=True
    )

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "role", "is_active", "password", "confirm_password"
        ]
        read_only_fields = ["is_active"]

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return data

    def create(self, validated_data):
        validated_data.pop("confirm_password", None)
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
# ============================================
# DEPARTMENT & SUBDEPARTMENT SERIALIZERS
# ============================================

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "description"]


class SubDepartmentSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = SubDepartment
        fields = ["id", "name", "description", "department", "department_name"]
        
class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "description", "hierarchy_level"]


# ============================================
# EMPLOYEE SERIALIZERS
# ============================================

class EmployeeSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    sub_department_name = serializers.CharField(source="sub_department.name", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_code",
            "full_name",
            "phone_number",
            "date_of_joining",
            "department",
            "department_name",
            "sub_department",
            "sub_department_name",
            "job_position",
            "employment_type",
            "gender",
            "marital_status",
            "job_status",
            "national_id",
            "date_of_birth",
            "address",
            "next_of_kin_name",
            "next_of_kin_relationship",
            "next_of_kin_phone",
            "documents",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["employee_code", "created_at", "updated_at"]

    def create(self, validated_data):
        return Employee.objects.create(**validated_data)

    def update(self, instance, validated_data):
        # Update all editable fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    

class EmployeeProfileSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    sub_department_name = serializers.CharField(source="sub_department.name", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_code",
            "full_name",
            "phone_number",
            "department",
            "department_name",
            "sub_department",
            "sub_department_name",
            "job_position",
            "employment_type",
            "gender",
            "marital_status",
            "job_status",
            "date_of_joining",
            "address",
            "image_url",
        ]

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            return request.build_absolute_uri(obj.image.url)
        return None

