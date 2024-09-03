from rest_framework import serializers
from .models import Tenant
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify

from django_tenants.utils import schema_context
from django_tenants.utils import tenant_context
from companies.models import UserProfile

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
        user = User.objects.create_user(
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
    frontend_url = serializers.URLField(required=False)

    class Meta:
        model = Tenant
        fields = ['company_name', 'user', 'frontend_url']

    def validate_company_name(self, value):
        if Tenant.objects.filter(company_name__iexact=value).exists():
            raise serializers.ValidationError("A tenant with this company name already exists.")
        return value

    def validate_schema_name(self, value):
        schema_name = slugify(value)
        if Tenant.objects.filter(schema_name__iexact=schema_name).exists():
            raise serializers.ValidationError("A tenant with this schema name already exists.")
        return schema_name

    def validate(self, data):
        user_data = data.get('user', {})
        if not user_data:
            raise serializers.ValidationError({"user": "User data is required."})

        user_serializer = UserSerializer(data=user_data)
        if not user_serializer.is_valid():
            raise serializers.ValidationError({"user": user_serializer.errors})

        # Validate email uniqueness
        email = user_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})

        return data

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        
        # Create Tenant first
        schema_name = self.validate_schema_name(validated_data['company_name'])
        tenant = Tenant.objects.create(
            schema_name=schema_name,
            company_name=validated_data['company_name']
        )

        # Generate username based on company name if not provided
        if 'username' not in user_data:
            user_data['username'] = generate_default_username(validated_data['company_name'])

        # Create User within Tenant context
        with tenant_context(tenant):
            user_serializer = UserSerializer(data=user_data)
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()

            # Associate user with tenant
            tenant.user = user
            tenant.save()

        return tenant
    
    