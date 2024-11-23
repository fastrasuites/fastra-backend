from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from users.models import TenantUser
from users.serializers import TenantUserSerializer
# from accounting.models import TenantUser
from .models import Tenant, UserProfile
from django.contrib.auth.models import User, Group
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify

from django_tenants.utils import schema_context
from django_tenants.utils import tenant_context

from .utils import generate_otp


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['is_verified']
        read_only_fields = ['is_verified']


def generate_default_username(company_name):
    company_name_parts = company_name.split()
    return f"admin_{slugify('_'.join(company_name_parts))}"


class UserSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    profile = UserProfileSerializer(required=False, read_only=True)

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'email', 'profile']
        extra_kwargs = {
            'username': {'required': False}
        }

    def validate(self, attrs):
        if attrs['password1'] != attrs['password2']:
            raise serializers.ValidationError({"password2": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_superuser(
            username=validated_data.get('username'),
            email=validated_data['email'],
            password=validated_data['password1']
        )
        return user

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['is_verified'] = instance.profile.is_verified if hasattr(instance, 'profile') else False
        return ret


class TenantRegistrationSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    company_name = serializers.CharField(required=True)

    class Meta:
        model = Tenant
        fields = ['company_name', 'user']

    def validate_company_name(self, value):
        if Tenant.objects.filter(company_name__iexact=value).exists():
            raise serializers.ValidationError("A tenant with the provided company name already exists.")
        return value

    def validate(self, data):
        user_data = data.get('user', {})
        if not user_data:
            raise serializers.ValidationError({"user": "User data is required."})

        user_serializer = UserSerializer(data=user_data)
        if not user_serializer.is_valid():
            raise serializers.ValidationError({"user": user_serializer.errors})

        email = user_data.get('email')
        if email:
            existing_user = User.objects.filter(email=email).first()
            if existing_user:
                user_profile = existing_user.profile
                if not user_profile.allow_multiple_tenants:
                    raise serializers.ValidationError({"email": "A user with this email already exists."})
                tenant_count = Tenant.objects.filter(created_by=existing_user).count()
                if tenant_count >= user_profile.max_tenants:
                    raise serializers.ValidationError({"email": "This user has reached the maximum allowed tenants."})

        return data

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        otp, hashed_otp = generate_otp()
        email = user_data.get('email')
        password = user_data.get('password1')
        # password = make_password(password)

        if 'username' not in user_data:
            user_data['username'] = generate_default_username(validated_data['company_name'])

        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            user = existing_user
        else:
            user_serializer = UserSerializer(data=user_data)
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()

        schema_name = slugify(validated_data['company_name'])
        tenant = Tenant.objects.create(
            schema_name=schema_name,
            company_name=validated_data['company_name'],
            otp=hashed_otp,
            otp_requested_at=timezone.now(),
            created_by=user,
            is_verified=False
        )
        tenant.save()
        with tenant_context(tenant):
            admin_group, created = Group.objects.get_or_create(name='Admin')
            tenant_user = TenantUser.objects.create(
                user_id=user.id,
                tenant=tenant,
                role=admin_group,
                # password=password
            )
            tenant_user.set_tenant_password(password)
            tenant_user.save()
        return tenant, otp