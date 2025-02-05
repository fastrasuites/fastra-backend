from rest_framework import serializers
from .models import Tenant, CompanyProfile
# from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify


# RESET PASSWORD
class RequestForgottenPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

class ForgottenPasswordSerializer(serializers.Serializer):
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