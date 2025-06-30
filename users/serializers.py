import uuid
from rest_framework import serializers
from django.contrib.auth.models import User, Group, Permission
import re
from django.utils.translation import gettext as _
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.contrib.auth.password_validation import validate_password

from core.errors.exceptions import TenantNotFoundException
from registration.models import AccessRight, Tenant
from users.models import AccessGroupRight, AccessGroupRightUser, TenantUser
from django.db import transaction

from users.utils import convert_to_base64, generate_access_code_for_access_group, generate_random_password
from django_tenants.utils import schema_context
from django.contrib.contenttypes.models import ContentType


# from accounting.models import TenantUser

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
    groups = serializers.HyperlinkedRelatedField(queryset=Group.objects.all(), many=True, view_name='group-detail',
                                                 required=False)

    class Meta:
        model = TenantUser
        fields = ['url', 'id', 'user', 'role', 'phone_number', 'language', 'timezone',
                  'in_app_notifications', 'email_notifications', 'groups']

    def validate(self, data):
        user_data = data.get('user', {})
        tenant_details = data.get('tenant_details', {})
        if not user_data:
            raise serializers.ValidationError({"user": "User data is required."})

        user_serializer = UserSerializer(data=user_data)
        if not user_serializer.is_valid():
            raise serializers.ValidationError({"user": user_serializer.errors})

        email = user_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})

        tenant_schema_name = tenant_details.schema_name
        if tenant_schema_name and Tenant.objects.filter(schema_name=tenant_schema_name).exists():
            raise serializers.ValidationError({"Tenant schema name": "No Tenant schema or tenant doesnt exist"})
        
        tenant_id = tenant_details.tenant_id
        if tenant_id:
            raise serializers.ValidationError({"tenant id": "Tenant id is required"}) 
        
        username = user_data.get('username')
        if username and not re.match(r'^[a-zA-Z\s]+$', username):
            raise serializers.ValidationError(
                {"username": _("Enter a valid username. This value may contain only letters and spaces.")})

        return data

    def create(self, validated_data):
        tenant_details = validated_data.pop('tenant_details')
        tenant = Tenant.objects.get(schema_name=tenant_details.schema_name)
        if not tenant:
            raise TenantNotFoundException()
         
        user_data = validated_data.pop('user')
        groups = validated_data.pop('groups', [])
        user_serializer = UserSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()
        tenant_user = TenantUser.objects.create(user=user.id, tenant=tenant, **validated_data)
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
    


# START THE VIEWS FOR THE NEW TENANT USER ACCOUNT
class NewTenantUserSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True) 
    access_codes = serializers.ListField(required=False, write_only=True)
    name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    temp_password = serializers.CharField(read_only=True)
    signature_image = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = TenantUser
        fields = ['id', 'user_id', 'name', 'email', 'role', 'phone_number', 'language', 'timezone',
                  'in_app_notifications', 'email_notifications', 'access_codes', 'temp_password', 'date_created',
                  'signature', 'signature_image']
        extra_kwargs = {'signature': {'read_only': True}}


    def get_user(self, obj):
        try:
            user = None
            with schema_context('public'):
                user = User.objects.get(id=obj.user_id)
                return {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name
                }
        except User.DoesNotExist:
            return None

    def validate_groups(self, value):
        # we are automatically converting each item to uppercase
        return [item.upper() for item in value]    
    
    def validate_email(self, value):
        if self.context['request'].method == "PATCH":
            return value

        with schema_context('public'):
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError("This email already exists")
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        tenant_schema_name = validated_data.pop('tenant_schema_name')
        tenant = Tenant.objects.get(schema_name=tenant_schema_name)
        if not tenant:
            raise TenantNotFoundException()
        
        password = generate_random_password()
        name_list = validated_data["name"].strip().split(' ')
        first_name = validated_data["name"]
        last_name = None
        if len(name_list) > 1:
            first_name = name_list[0]
            last_name = name_list[1]

        new_user = None
        username = f"{first_name[:4]}_{uuid.uuid4().hex[:8]}"

        with schema_context('public'):
            new_user = User.objects.create(email=validated_data["email"], password=password, username=username,
                                           first_name=first_name, last_name=last_name)
            new_user.set_password(password)
            new_user.save()

        validated_data["temp_password"] = password
        validated_data["password"] = new_user.password
        
        access_codes = validated_data.pop('access_codes', [])
        validated_data.pop('name')
        validated_data.pop('email')
        validated_data.pop('signature_image', None)
        
        tenant_user = TenantUser.objects.create(user_id=new_user.id, tenant=tenant, **validated_data)

        access_group_right_user = [AccessGroupRightUser(
            access_code = code,
            user_id = tenant_user.user_id
        ) for code in access_codes]

        results = AccessGroupRightUser.objects.bulk_create(access_group_right_user)
        return tenant_user

    @transaction.atomic
    def update_user_information(self, instance, validated_data):
        user = None
        tenant_user = instance

        with schema_context('public'):
            if not User.objects.filter(id=instance.user_id).exists():
                raise serializers.ValidationError({"detail": "User does not exists"})
            user = User.objects.get(id=instance.user_id)

        if validated_data.get("name", None) is not None:
            name_list = validated_data["name"].strip().split(' ')
            first_name = validated_data["name"]
            last_name = None
            if len(name_list) > 1:
                first_name = name_list[0]
                last_name = name_list[1]
            user.first_name = first_name
            user.last_name = last_name

        if validated_data.get("email", None) is not None:
            user.email = validated_data.get("email")

        if validated_data.get("role", None) is not None:
            tenant_user.role = validated_data["role"]

        if validated_data.get("phone_number", None) is not None:
            tenant_user.phone_number = validated_data["phone_number"]

        if validated_data.get("in_app_notifications", None) is not None:
            tenant_user.in_app_notifications = validated_data["in_app_notifications"]
        
        if validated_data.get("email_notifications", None) is not None:
            tenant_user.email_notifications = validated_data["email_notifications"]
        
        if validated_data.get("signature_image", None) is not None:
            tenant_user.signature = convert_to_base64(validated_data["signature_image"])
        
        if validated_data.get("access_codes", None) is not None:
            access_codes = validated_data.pop("access_codes")

            access_group_right_user = [AccessGroupRightUser(
            access_code = code,
            user_id = tenant_user.user_id
            ) for code in access_codes]

            AccessGroupRightUser.objects.filter(user_id=tenant_user.user_id).delete()
            results = AccessGroupRightUser.objects.bulk_create(access_group_right_user)
        
        tenant_user.save()
        with schema_context('public'):
            user.save()

        return tenant_user

class ChangePasswordSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(write_only=True, required=True)
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        if not TenantUser.objects.filter(user_id=data["user_id"]).exists():
            raise serializers.ValidationError({"detail": "This user does not exists"})
        tenant_user = TenantUser.objects.get(user_id=data["user_id"])
        if tenant_user.temp_password != data["old_password"]:
            raise serializers.ValidationError({"detail": "Incorrect Old Password !!!"})
        
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"detail": "Passwords do not match."})              
        return data
    
    
    def change_password(self, validated_data):
        try:
            user = None
            with schema_context('public'):
                user = User.objects.get(id=validated_data["user_id"])
            tenant_user = TenantUser.objects.get(user_id=validated_data["user_id"])

            user.set_password(validated_data["new_password"])
            tenant_user.password = user.password
            tenant_user.temp_password = None

            with transaction.atomic():
                tenant_user.save()
                with schema_context('public'):
                    user.save()
            return {"detail": "Password changed successfully"}
    
        except Exception as e:
            raise serializers.ValidationError(f"Failed to change password: {str(e)}")
    # END THE VIEWS FOR THE NEW TENANT USER ACCOUNT


# START THE ACCESSGROUP RIGHT SERIALIZER
class AccessGroupRightSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(max_length=20, required=True)
    access_rights = serializers.ListField(child=serializers.DictField(), required=True, write_only=True)

    class Meta:
        model = AccessGroupRight
        fields = ["id", "access_code", "group_name", "application", 
                  "application_module", "access_rights", "access_right", "date_updated", "date_created"]
        read_only_fields = ["id", "access_right", "access_code"]

    def validate_access_rights(self, value):
        for item in value:
            module = item.get("module")
            rights = item.get("rights")

            if not isinstance(module, str):
                raise serializers.ValidationError(f"Invalid module Type: {module}")

            if not isinstance(rights, list) or not all(isinstance(r, int) for r in rights):
                raise serializers.ValidationError(f"Rights must be a list of integers: {rights}")

            # Optional: Validate right existence
            for right_id in rights:
                if not AccessRight.objects.filter(id=right_id).exists():
                    raise serializers.ValidationError(f"AccessRight with ID {right_id} does not exist.")

        return value
    
    
    def validate_application(self, value):
        if not ContentType.objects.filter(app_label__icontains=value).exists():
            raise serializers.ValidationError(f"{value} module does not exist.")
        return value

    def create(self, validated_data):
        group_name = validated_data["group_name"].strip().upper()
        application = validated_data["application"]
        access_rights = validated_data["access_rights"]

        access_code = generate_access_code_for_access_group(application, group_name)
        access_groups = []
        for action in access_rights:
            module = action["module"]
            rights = action["rights"]

            for right_id in rights:
                access_group = AccessGroupRight(
                    group_name=group_name.upper(),
                    application=application.lower(),
                    access_code=access_code,
                    application_module=module.lower(),
                    access_right_id=right_id
                )
                try:
                    access_group.full_clean(exclude=["date_created", "date_updated"])
                    access_groups.append(access_group)
                    from django.core.exceptions import ValidationError

                except ValidationError as ve:
                    raise serializers.ValidationError(f"Validation failed for access group: {ve}")

        with transaction.atomic():
            AccessGroupRight.objects.bulk_create(access_groups)

        return {
            "detail": "Access Group Created Successfully",
            "group_name": group_name
        }
# END THE ACCESSGROUP RIGHT SERIALIZER