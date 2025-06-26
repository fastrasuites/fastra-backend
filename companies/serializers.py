# from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify

from rest_framework import serializers

from .models import CompanyRole, Tenant, CompanyProfile


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
    otp = serializers.CharField(required=True, max_length=4, min_length=4)

class ForgottenPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

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


        
class CompanyRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyRole
        fields = ['id', 'name']


class CompanyProfileSerializer(serializers.ModelSerializer):
    roles = CompanyRoleSerializer(many=True, required=False)

    class Meta:
        model = CompanyProfile
        fields = [
            'logo', 'phone', 'street_address', 'city', 'state', 'country',
            'registration_number', 'tax_id', 'industry', 'language',
            'company_size', 'website', 'roles'
        ]

    def update(self, instance, validated_data):
        roles_data = validated_data.pop('roles', [])

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
