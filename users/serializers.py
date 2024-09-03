# from rest_framework import serializers
# from django.contrib.auth.models import User
# from .models import TenantUser, TenantPermission, UserPermission

# class UserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ['id', 'username', 'email',]
#         extra_kwargs = {'password': {'write_only': True, 'required': True} }

# class TenantUserSerializer(serializers.ModelSerializer):
#     user = UserSerializer()

#     class Meta:
#         model = TenantUser
#         fields = ['id', 'user', 'tenant', 'role', 'phone_number', 'language', 'timezone', 
#                   'in_app_notifications', 'email_notifications', 'signature']

#     def create(self, validated_data):
#         user_data = validated_data.pop('user')
#         user = User.objects.create_user(**user_data)
#         tenant_user = TenantUser.objects.create(user=user, **validated_data)
#         return tenant_user

#     def update(self, instance, validated_data):
#         user_data = validated_data.pop('user', None)
#         if user_data:
#             user_serializer = UserSerializer(instance.user, data=user_data, partial=True)
#             if user_serializer.is_valid():
#                 user_serializer.save()
#         return super().update(instance, validated_data)

# class TenantPermissionSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = TenantPermission
#         fields = ['id', 'tenant', 'name', 'description']

# class UserPermissionSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = UserPermission
#         fields = ['id', 'user', 'permission']