from rest_framework import serializers
from .models import Tenant, CompanyProfile
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify
from .models import UserProfile

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['is_verified']
        read_only_fields = ['is_verified']

def generate_default_username(company_name):
    company_name_parts = company_name.split()
    return f"admin_{slugify(company_name_parts)}"

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

    class Meta:
        model = Tenant
        fields = ['company_name', 'user']

    def validate_company_name(self, value):
        if Tenant.objects.filter(company_name__iexact=value).exists():
            raise serializers.ValidationError("A tenant with this company name already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_schema_name(self, value):
        if Tenant.objects.filter(schema_name__iexact=value).exists():
            raise serializers.ValidationError("A tenant with this schema name already exists.")
        return value

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
        user_data['username'] = generate_default_username(validated_data['company_name'])
        
        user_serializer = UserSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()

        schema_name = slugify(validated_data['company_name'])
        tenant = Tenant.objects.create(
            schema_name=schema_name,
            company_name=validated_data['company_name'],
            user=user
        )
        
        return tenant

    

# LOGIN
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)


# RESET PASSWORD
class RequestPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, max_length=4, min_length=4)
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



class CompanyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyProfile
        fields = ['logo', 'phone', 'address', 'city', 'state', 'zip_code', 'country', 
                  'registration_number', 'tax_id', 'currency', 'industry', 'language', 'time_zone']