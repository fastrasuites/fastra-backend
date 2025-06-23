from django.shortcuts import get_object_or_404, render
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, generics, filters
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import Group, Permission, User

from .models import TenantUser
from .serializers import ChangePasswordSerializer, NewTenantUserSerializer, UserSerializer, TenantUserSerializer, GroupSerializer, PermissionSerializer, \
    GroupPermissionSerializer, PasswordChangeSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.sites.shortcuts import get_current_site
from .utils import Util, generate_access_code_for_access_group, generate_random_password
from django_tenants.utils import schema_context
from django.db import transaction
from .utils import convert_to_base64
from .models import AccessGroupRight
from .serializers import AccessGroupRightSerializer
from rest_framework.exceptions import ValidationError
from rest_framework import serializers

class SoftDeleteWithModelViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return super().get_queryset()

    def perform_destroy(self, instance):
        instance.is_hidden = True
        instance.save()

    @action(detail=True, methods=['get', 'post'])
    def toggle_hidden(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        instance.is_hidden = not instance.is_hidden
        instance.save()
        return Response({'status': f'Hidden status set to {instance.is_hidden}'}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False)
    def hidden(self, request, *args, **kwargs):
        hidden_instances = self.queryset.filter(is_hidden=True)
        page = self.paginate_queryset(hidden_instances)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(hidden_instances, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def active(self, request, *args, **kwargs):
        active_instances = self.queryset.filter(is_hidden=False)
        page = self.paginate_queryset(active_instances)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(active_instances, many=True)
        return Response(serializer.data)


class SearchDeleteViewSet(SoftDeleteWithModelViewSet):
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = []

    @action(detail=False)
    def search(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_hidden=False)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class TenantUserViewSet(SearchDeleteViewSet):
    queryset = TenantUser.objects.all()
    serializer_class = TenantUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['user__username', 'user__email']

    def perform_create(self, serializer):
        tenant_user = serializer.save()
        self.send_verification_email(tenant_user)

    def get_user_email(self, tenant_user):
        if hasattr(tenant_user, 'user') and hasattr(tenant_user.user, 'email'):
            return tenant_user.user.email
        elif 'email' in self.request.data:
            return self.request.data['email']
        else:
            raise ValueError("No email address available for verification")

    def send_verification_email(self, tenant_user):
        try:
            email = self.get_user_email(tenant_user)
        except ValueError as e:
            print(f"Error: {str(e)}")
            return

        token = RefreshToken.for_user(tenant_user)
        token['email'] = email

        current_site = get_current_site(self.request).domain
        verification_url = f'https://{current_site}/email-verify?token={str(token.access_token)}'

        email_body = f'Hi {tenant_user.user.username},\n\nUse the link below to verify your email:\n{verification_url}'
        email_data = {
            'email_body': email_body,
            'to_email': email,
            'email_subject': 'Verify Your Email'
        }
        Util.send_email(email_data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant_user = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({
            'detail': 'Tenant user created successfully. If an email was provided, a verification link has been sent.',
            'user': serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

    def sync_user_permissions(self, user):
        # Get all permissions from the user's groups
        group_permissions = Permission.objects.filter(group__user=user).distinct()

        # Add these permissions to the user's direct permissions
        user.user_permissions.set(group_permissions)

    @action(detail=True, methods=['post'])
    def add_groups(self, request, pk=None):
        tenant_user = self.get_object()
        user = tenant_user.user
        groups = Group.objects.filter(id__in=request.data.get('groups', []))
        user.groups.add(*groups)
        self.sync_user_permissions(user)
        return Response({'status': 'Groups added and permissions synced'})

    @action(detail=True, methods=['post'])
    def remove_groups(self, request, pk=None):
        tenant_user = self.get_object()
        user = tenant_user.user
        groups = Group.objects.filter(id__in=request.data.get('groups', []))
        user.groups.remove(*groups)
        self.sync_user_permissions(user)
        return Response({'status': 'Groups removed and permissions synced'})

    def perform_update(self, serializer):
        tenant_user = serializer.save()
        self.sync_user_permissions(tenant_user.user)

    @action(detail=True, methods=['post'])
    def change_password(self, request, pk=None):
        tenant_user = self.get_object()
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = tenant_user.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    search_fields = ['name']


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    search_fields = ['name', 'codename']

    def get_queryset(self):
        app_label = self.request.query_params.get('app', None)
        if app_label:
            return Permission.objects.filter(content_type__app_label=app_label)
        return Permission.objects.all()


class GroupPermissionViewSet(viewsets.ModelViewSet):
    serializer_class = GroupPermissionSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get_queryset(self):
        # Return an empty queryset or implement logic if needed
        return Group.objects.none()

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = serializer.validated_data['group']
        permissions = serializer.validated_data['permissions']
        group.permissions.set(permissions)

        # Return permission names instead of IDs
        permission_names = [perm.name for perm in permissions]

        return Response({
            'group': group.id,
            'permissions': permission_names  # Return names instead of IDs
        }, status=status.HTTP_201_CREATED)

    # @action(detail=False, methods=['get'])
    # def group_permissions(self, request):
    #     group_id = request.query_params.get('group_id')
    #     if not group_id:
    #         return Response({"error": "group_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    #     try:
    #         group = Group.objects.get(id=group_id)
    #     except Group.DoesNotExist:
    #         return Response({"error": "Group not found"}, status=status.HTTP_404_NOT_FOUND)

    #     permissions = group.permissions.all()

    #     # Return permission names instead of full objects or IDs
    #     permission_names = [perm.name for perm in permissions]

    #     return Response({'permissions': permission_names})


class PasswordChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PasswordChangeSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


# START TO CREATE AN ACCOUNT THAT BELONGS TO A PARTICULAR TENANT
class NewTenantUserViewSet(SearchDeleteViewSet):
    queryset = TenantUser.objects.all()
    serializer_class = NewTenantUserSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    search_fields = ['user__username', 'user__email']

    def get_user_email(self, tenant_user):
        if hasattr(tenant_user, 'user') and hasattr(tenant_user.user, 'email'):
            return tenant_user.user.email
        elif 'email' in self.request.data:
            return self.request.data['email']
        else:
            raise ValueError("No email address available for verification")

    def send_verification_email(self, tenant_user):
        try:
            email = self.get_user_email(tenant_user)
        except ValueError as e:
            print(f"Error: {str(e)}")
            return

        token = RefreshToken.for_user(tenant_user)
        token['email'] = email

        current_site = get_current_site(self.request).domain
        verification_url = f'https://{current_site}/email-verify?token={str(token.access_token)}'

        email_body = f'Hi {tenant_user.user.username},\n\nUse the link below to verify your email:\n{verification_url}'
        email_data = {
            'email_body': email_body,
            'to_email': email,
            'email_subject': 'Verify Your Email'
        }
        Util.send_email(email_data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant_schema_name = request.auth["schema_name"]
        serializer.validated_data["tenant_schema_name"] = tenant_schema_name
        if 'signature_image' in serializer.validated_data:
            serializer.validated_data["signature"] = convert_to_base64(serializer.validated_data["signature_image"])
        tenant_user = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.validated_data)
        return Response({
            'detail': 'Tenant user created successfully. If an email was provided, a verification link has been sent.',
            'user': serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)


    def reset_password(self, request, pk=None):
        try:
            email = request.data.get("email", None)
            user = None
            with schema_context('public'):
                user = User.objects.get(email=email)

            tenant_user = TenantUser.objects.get(user_id=user.id)
            new_password = generate_random_password()
            user.set_password(new_password) #The reason we have this is to has the password and then save into the db where commit=False for now
            tenant_user.password = user.password         
            tenant_user.temp_password = new_password

            with transaction.atomic():
                tenant_user.save()
                with schema_context('public'):
                    user.save()

            return Response({'detail': f'Password reset successfully. New Password is {new_password}'}, status=status.HTTP_200_OK)
        except Exception as ex:
            return Response({"detail": str(ex)}, status=status.HTTP_400_BAD_REQUEST)



class NewTenantPasswordViewSet(SearchDeleteViewSet):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['user__username', 'user__email']

    def get_object(self):
        return TenantUser.objects.get(user=self.request.user)
    
    def change_password(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.change_password(serializer.validated_data)
            return Response(result, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)        


class NewTenantProfileViewSet(SearchDeleteViewSet):
    queryset = TenantUser.objects.all()
    serializer_class = NewTenantUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

    def update_user_information(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=True)
        # Validate incoming data
        serializer.is_valid(raise_exception=True)
        serializer.update_user_information(instance, serializer.validated_data)
        
        refreshed_serializer = self.get_serializer(instance)
        return Response(refreshed_serializer.data, status=status.HTTP_200_OK)


# END TO CREATE AN ACCOUNT THAT BELONGS TO A PARTICULAR TENANT



# START THE CREATION OF ACCESS GROUP
class AccessGroupRightViewSet(SoftDeleteWithModelViewSet):
    queryset = AccessGroupRight.objects.filter(is_hidden=False) # type: ignore
    serializer_class = AccessGroupRightSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'access_code'

    def get_object(self):
        access_code = self.kwargs.get(self.lookup_field)
        return get_object_or_404(AccessGroupRight, access_code=access_code)
    
    def retrieve(self, request, access_code=None):
        # Use .filter() to get multiple results
        queryset = AccessGroupRight.objects.filter(access_code=access_code)
        if not queryset.exists():
            return Response({"detail": "No records found for this access code."}, status=status.HTTP_404_NOT_FOUND)

        # Use a serializer that returns many=True
        serializer = AccessGroupRightSerializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = AccessGroupRightSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
  
    
    def partial_update(self, request, access_code=None):
        data = request.data

        group_name = data.get("group_name", None)
        application_id = data.get("application_id", None)
        application_name = data.get("application_name", "")

        access_rights = data.get("access_rights", None)

        if not AccessGroupRight.objects.filter(access_code=access_code).exists():
            return Response({"detail": "Access group does not exist for the specified application"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            if access_rights is not None:
                # Delete old rights
                AccessGroupRight.objects.filter(access_code=access_code).delete()

                access_code = access_code
                access_groups = []

                for action in access_rights:
                    if action.get("module", None) is None and action.get("rights", None) is None:
                        return Response({"detail": "Both module and rights key must be provided"}, status=status.HTTP_400_BAD_REQUEST)

                    module_id = action["module"]
                    rights = action["rights"]

                    for right_id in rights:
                        access_group = AccessGroupRight(
                            group_name=group_name,
                            application_id=application_id,
                            access_code=access_code,
                            application_module_id=module_id,
                            access_right_id=right_id
                        )
                        try:
                            access_group.full_clean(exclude=["date_created", "date_updated"])
                            access_groups.append(access_group)

                        except ValidationError as ve:
                            raise serializers.ValidationError(f"Validation failed for access group: {ve}")

                
                AccessGroupRight.objects.bulk_create(access_groups)

        return Response({"detail": "Access Group Updated Successfully"}, status=status.HTTP_200_OK)


    def destroy(self, request, *args, **kwargs):
        access_code = kwargs.get(self.lookup_field)

        # Example: Delete all rows with the same access_code
        queryset = self.queryset.filter(access_code=access_code)
        if not queryset.exists():
            raise Response({"detail": "No access group found with this access code."})
        queryset.delete()
        return Response(
            {"detail": f"Access group deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
# END THE CREATION OF ACCESS GROUP