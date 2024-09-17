from rest_framework import serializers,status
from django.contrib.auth.models import User, Group , Permission
from .models import TenantUser
import re
from django.utils.translation import gettext as _
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.contrib.auth.password_validation import validate_password

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename']


class GroupSerializer(serializers.ModelSerializer):
    # permissions = PermissionSerializer(many=True, read_only=False)

    class Meta:
        model = Group
        fields = ['id', 'name', ]

    # def create(self, validated_data):
    #     permissions_data = validated_data.pop('permissions', [])
    #     group = Group.objects.create(**validated_data)
    #     for permission_data in permissions_data:
    #         permission = Permission.objects.get(id=permission_data['id'])
    #         group.permissions.add(permission)
    #     return group

    # def update(self, instance, validated_data):
    #     permissions_data = validated_data.pop('permissions', [])
    #     instance.name = validated_data.get('name', instance.name)
    #     instance.save()
        
    #     # Clear existing permissions and add new ones
    #     instance.permissions.clear()
    #     for permission_data in permissions_data:
    #         permission = Permission.objects.get(id=permission_data['id'])
    #         instance.permissions.add(permission)
    #     return instance

class GroupPermissionSerializer(serializers.Serializer):
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all())
    permissions = serializers.PrimaryKeyRelatedField(queryset=Permission.objects.all(), many=True, )

    def update(self, instance, validated_data):
        group = validated_data['group']
        permissions = validated_data['permissions']
        group.permissions.set(permissions)
        return {'group': group, 'permissions': permissions}



class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'password', 'confirm_password']
        extra_kwargs = {
            'password': {'write_only': True},  # Ensure password is write-only
        }

    def validate(self, data):
        """
        Validate that the passwords match.
        """
        password = data.get('password')
        confirm_password = data.get('confirm_password')

        if password != confirm_password:
            raise serializers.ValidationError("Passwords do not match.")
        

        return data

    def validate_email(self, value):
        """
        Validate that the email is provided, valid, and unique.
        """
        if not value:
            raise serializers.ValidationError("This field is required.")

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")

        return value

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = User.objects.create_superuser(
            username=validated_data.get('username'),
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=validated_data['password']
        )
        return user




class TenantUserSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    groups = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), many=True, required=False)

    class Meta:
        model = TenantUser
        fields = ['id', 'user', 'role', 'phone_number', 'language', 'timezone', 
                  'in_app_notifications', 'email_notifications', 'groups']


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
        groups = validated_data.pop('groups', [])
        user_serializer = UserSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()
        tenant_user = TenantUser.objects.create(user=user, **validated_data)
        
        # Set additional groups
        user.groups.add(*groups)

        # groups = validated_data.get('group', [])
        # tenant_user.role.set(groups)  # Set the initial roles
        return tenant_user
    

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)
        if user_data:
            user_serializer = UserSerializer(instance.user, data=user_data, partial=True)
            if user_serializer.is_valid():
                user_serializer.save()
        
        # Additional groups
        groups = validated_data.pop('groups', None)
        if groups is not None:
            instance.user.groups.add(*groups)  


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







# class UserManagementView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         if self.request.user.id == User.objects.first().id:  # Check if the user is the first (admin) user
#             return User.objects.all()
#         else:
#             return User.objects.filter(id=self.request.user.id)

#     def get(self, request):
#         users = self.get_queryset()
#         serializer = UserSerializer(users, many=True)
#         return Response(serializer.data)

#     def post(self, request):
#         serializer = UserSerializer(data=request.data)
#         if serializer.is_valid():
#             user = serializer.save()
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     def put(self, request, pk=None):
#         user = User.objects.get(pk=pk)
#         if request.user.id == User.objects.first().id:  # Check if the user is the first (admin) user
#             user.is_archived = not user.is_archived
#             user.save()
#             serializer = UserSerializer(user)
#             return Response(serializer.data)
#         else:
#             return Response({'error': 'Only admin users can archive/unarchive users.'}, status=status.HTTP_403_FORBIDDEN)

#     def delete(self, request, pk=None):
#         user = User.objects.get(pk=pk)
#         if user.id == request.user.id or request.user.id == User.objects.first().id:  # Allow deletion by the user or admin
#             user.delete()
#             return Response(status=status.HTTP_204_NO_CONTENT)
#         else:
#             return Response({'error': 'You can only delete users you have created.'}, status=status.HTTP_403_FORBIDDEN)
