from rest_framework import serializers
from django.contrib.auth.models import User, Group, Permission
from .models import TenantUser
import re
from django.utils.translation import gettext as _
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.contrib.auth.password_validation import validate_password

class PermissionSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='permission-detail')

    class Meta:
        model = Permission
        fields = ['url', 'id', 'name', 'codename']

    def create(self, validated_data):
        return Permission.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.codename = validated_data.get('codename', instance.codename)
        instance.save()
        return instance

class GroupSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='group-detail')

    class Meta:
        model = Group
        fields = ['url', 'id', 'name']

    def create(self, validated_data):
        return Group.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.save()
        return instance

class GroupPermissionSerializer(serializers.Serializer):
    url = serializers.HyperlinkedIdentityField(view_name='group-permissions-detail')
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all())
    permissions = serializers.PrimaryKeyRelatedField(queryset=Permission.objects.all(), many=True, write_only=True)
    permission_names = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Group
        fields = ['url', 'group', 'permissions', 'permission_names']

    def get_permission_names(self, instance):
        return [perm.name for perm in instance.permissions.all()]

    def create(self, validated_data):
        group = validated_data['group']
        permissions = validated_data['permissions']
        group.permissions.set(permissions)
        return group

    def update(self, instance, validated_data):
        permissions = validated_data.get('permissions', instance.permissions.all())
        instance.permissions.set(permissions)
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['permission_names'] = self.get_permission_names(instance)
        return representation

class UserSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='user-detail')
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['url', 'id', 'username', 'first_name', 'last_name', 'email', 'password', 'confirm_password']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate(self, data):
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("This field is required.")
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = User.objects.create_user(
            username=validated_data.get('username'),
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=validated_data['password']
        )
        return user

    def update(self, instance, validated_data):
        instance.username = validated_data.get('username', instance.username)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.email = validated_data.get('email', instance.email)
        if 'password' in validated_data:
            instance.set_password(validated_data['password'])
        instance.save()
        return instance

class TenantUserSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='tenant-user-detail')
    user = UserSerializer()
    # user = serializers.HyperlinkedRelatedField(view_name='user-detail', queryset=User.objects.all())
    groups = serializers.HyperlinkedRelatedField(queryset=Group.objects.all(), many=True, view_name='group-detail', required=False)

    class Meta:
        model = TenantUser
        fields = ['url', 'id', 'user', 'role', 'phone_number', 'language', 'timezone', 
                  'in_app_notifications', 'email_notifications', 'groups']

    def validate(self, data):
        user_data = data.get('user', {})
        if not user_data:
            raise serializers.ValidationError({"user": "User data is required."})

        user_serializer = UserSerializer(data=user_data)
        if not user_serializer.is_valid():
            raise serializers.ValidationError({"user": user_serializer.errors})

        email = user_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})

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
        user.groups.add(*groups)
        return tenant_user

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)
        if user_data:
            user_serializer = UserSerializer(instance.user, data=user_data, partial=True)
            if user_serializer.is_valid():
                user_serializer.save()
        
        groups = validated_data.pop('groups', None)
        if groups is not None:
            instance.user.groups.set(groups)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

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

    def create(self, validated_data):
        user = self.context['request'].user
        user.set_password(validated_data['new_password'])
        user.save()
        return user

    def update(self, instance, validated_data):
        instance.set_password(validated_data['new_password'])
        instance.save()
        return instance