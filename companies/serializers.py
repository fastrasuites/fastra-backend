# from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify

from rest_framework import serializers

from users.utils import convert_to_base64
from django.db import transaction

from .models import CompanyRole, Tenant, CompanyProfile
import json
# Verify Email
class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)

# Resend Verification Email
class ResendVerificationEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

# RESET PASSWORD
class RequestForgottenPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

class OTPVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(required=True, max_length=4, min_length=4)

class ForgottenPasswordSerializer(serializers.Serializer):
    #otp = serializers.CharField(required=True, max_length=4, min_length=4)
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField()

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})

        try:
            validate_password(attrs['new_password'])
        except serializers.ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})

        return attrs


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = '__all__'



"""class CompanyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyProfile
        fields = ['logo', 'phone', 'address', 'city', 'state', 'zip_code', 'country', 
                  'registration_number', 'tax_id', 'currency', 'industry', 'language', 'time_zone']
"""


class CompanyRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyRole
        fields = ['id', 'name']


class CompanyRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyRole
        fields = ['id', 'name']

    def validate_roles(self, value):
        print("✅ validate_roles received:", value)
        return value


class CompanyProfileSerializer(serializers.ModelSerializer):
    roles = CompanyRoleSerializer(many=True, required=False)
    logo_image = serializers.ImageField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = CompanyProfile
        fields = [
            'logo', 'logo_image', 'phone', 'street_address', 'city', 'state', 'country',
            'registration_number', 'tax_id', 'industry', 'language',
            'company_size', 'website', 'roles'
        ]
        extra_kwargs = {'logo': {'read_only': True}}

    @transaction.atomic
    def update(self, instance, validated_data):
        print(validated_data)
        roles_data = validated_data.pop('roles', [])
        # Handle logo_image properly
        logo_image = validated_data.pop('logo_image', None)
        if logo_image is not None:
            validated_data["logo"] = convert_to_base64(logo_image)
        
        # Update other profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Handle role creation without duplicates
        existing_names = instance.roles.values_list('name', flat=True)
        for role in roles_data:
            name = role.get("name", "").strip()
            if name and name.lower() not in [r.lower() for r in existing_names]:
                CompanyRole.objects.create(company=instance, name=name)

        return instance 


class ChangeAdminPasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)

