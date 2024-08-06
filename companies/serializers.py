from rest_framework import serializers
from .models import Tenant
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from .models import UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['is_verified']
        read_only_fields = ['is_verified']


class UserSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    profile = UserProfileSerializer(required=False, read_only=True)

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'email', 'profile']

    def validate(self, attrs):
        if attrs['password1'] != attrs['password2']:
            raise serializers.ValidationError("Passwords do not match.")
        return attrs

    def create(self, validated_data):

        profile_data = validated_data.pop('profile', {})
        validated_data.pop('password2')  # Remove password2 as it's not needed for User creation
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password1']
        )

        # The UserProfile is created automatically via the signal,
        # so we just need to update it with any provided data
        if profile_data:
            UserProfile.objects.filter(user=user).update(**profile_data)

        return user

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['is_verified'] = False  # Always set is_verified to False for new users
        return ret


class TenantRegistrationSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Tenant
        fields = ['schema_name', 'company_name', 'user']

    # VALIDATE DATAS
    def validate_company_name(self, value):
        if Tenant.objects.filter(company_name__iexact=value).exists():
            raise serializers.ValidationError("A tenant with this company name already exists.")
        return value

    def validate_shema_name(self, value):
        if Tenant.objects.filter(schema_name__iexact=value).exists():
            raise serializers.ValidationError("A tenant with this schema name already exists.")
        return value

    def validate(self, data):
        user_data = data.get('user', {})
        if not user_data:
            raise serializers.ValidationError("User data is required.")

        user_serializer = UserSerializer(data=user_data)
        if not user_serializer.is_valid():
            raise serializers.ValidationError(user_serializer.errors)

        return data

    # CREATE AFTER VALIDATION
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = UserSerializer.create(UserSerializer(), validated_data=user_data)
        tenant = Tenant.objects.create(user=user, **validated_data)
        return tenant


# LOGIN
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=True)
    password = serializers.CharField(max_length=128, write_only=True, required=True)


# RESET PASSWORD
class RequestPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField(read_only=True)
    token = serializers.CharField(read_only=True)
    password1 = serializers.CharField(write_only=True, required=True)
    password2 = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        if attrs['password1'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})

        try:
            validate_password(attrs['password1'])
        except serializers.ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})

        return attrs


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = '__all__'
