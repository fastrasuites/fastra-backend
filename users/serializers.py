from rest_framework import serializers,status
from django.contrib.auth.models import User
from .models import TenantUser, TenantPermission, UserPermission
import re
from django.utils.translation import gettext as _
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'is_archived']
        read_only_fields = ['is_archived']
        
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


class UserManagementView(APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.id == User.objects.first().id:  # Check if the user is the first (admin) user
            return User.objects.all()
        else:
            return User.objects.filter(id=self.request.user.id)

    def get(self, request):
        users = self.get_queryset()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        user = User.objects.get(pk=pk)
        if request.user.id == User.objects.first().id:  # Check if the user is the first (admin) user
            user.is_archived = not user.is_archived
            user.save()
            serializer = UserSerializer(user)
            return Response(serializer.data)
        else:
            return Response({'error': 'Only admin users can archive/unarchive users.'}, status=status.HTTP_403_FORBIDDEN)

    def delete(self, request, pk=None):
        user = User.objects.get(pk=pk)
        if user.id == request.user.id or request.user.id == User.objects.first().id:  # Allow deletion by the user or admin
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({'error': 'You can only delete users you have created.'}, status=status.HTTP_403_FORBIDDEN)


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


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(min_length=8, max_length=128, write_only=True)
    new_password = serializers.CharField(min_length=8, max_length=128, write_only=True)
    confirm_new_password = serializers.CharField(min_length=8, max_length=128, write_only=True)

    def validate(self, attrs):
        user = self.context['request'].user
        if not user.check_password(attrs['old_password']):
            raise serializers.ValidationError({'old_password': 'Incorrect password.'})

        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({'confirm_new_password': 'Passwords do not match.'})

        return attrs


class TenantPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantPermission
        fields = ['id', 'name', 'description']

class UserPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPermission
        fields = ['id', 'user', 'permission']