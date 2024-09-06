from rest_framework import serializers
from django.contrib.auth.models import User
from .models import TenantUser, TenantPermission, UserPermission
import re
from django.utils.translation import gettext as _


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username','first_name', 'last_name', 'email','password']
        
        extra_kwargs = {
            'username': {'required': True},
            'password': {'required': True, 'write_only': True},  # Ensure password is write-only
            'email': {'required': True, 'validators': []}  # Remove the default unique validator
        }

    def validate_email(self, value):
        """
        Validate that the email is provided, valid, and unique.
        """
        if not value:
            raise serializers.ValidationError("This field is required.")

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")

        return value


class TenantUserSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = TenantUser
        fields = ['id', 'user', 'role', 'phone_number', 'language', 'timezone', 
                  'in_app_notifications', 'email_notifications']


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

        # Validate username to allow letters and spaces only
        username = user_data.get('username')
        if username and not re.match(r'^[a-zA-Z\s]+$', username):
            raise serializers.ValidationError({"username": _("Enter a valid username. This value may contain only letters and spaces.")})


        return data


    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = User.objects.create_user(**user_data)
        tenant_user = TenantUser.objects.create(user=user, **validated_data)
        return tenant_user

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)
        if user_data:
            user_serializer = UserSerializer(instance.user, data=user_data, partial=True)
            if user_serializer.is_valid():
                user_serializer.save()
        return super().update(instance, validated_data)

class TenantPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantPermission
        fields = ['id', 'name', 'description']

class UserPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPermission
        fields = ['id', 'user', 'permission']