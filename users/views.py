from django.core.mail import EmailMessage
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
from .models import AccessGroupRight, AccessGroupRightUser
from .serializers import AccessGroupRightSerializer
from rest_framework.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from django.core.exceptions import ObjectDoesNotExist

from shared.viewsets.soft_delete_search_viewset import SoftDeleteWithModelViewSet, SearchDeleteViewSet


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

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        tenant_users = serializer.data

        for data in tenant_users:
            with schema_context("public"):
                user = User.objects.get(pk=data["user_id"])
                data["email"] = user.email
                data["first_name"] = user.first_name
                data["last_name"] = user.last_name
                data["last_login"] = user.last_login

        return Response(tenant_users)


    def retrieve(self, request, pk=None):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            data = serializer.data
            
            access_group_user = AccessGroupRightUser.objects.filter(user_id=instance.user_id)
            access_codes = None
            if not access_group_user.exists():
                access_codes = []
                with schema_context("public"):
                    user = User.objects.get(pk=instance.user_id)
                    data["email"] = user.email
                    data["first_name"] = user.first_name
                    data["last_name"] = user.last_name
                    data["last_login"] = user.last_login
                return Response(data)

            access_codes = [code.access_code for code in access_group_user]

            access_group = AccessGroupRight.objects.filter(
                access_code__in=access_codes
            ).distinct('access_code', 'group_name')
            access_group = list(access_group)
            access_groups = []
            for grp in access_group:
                access_dict = {
                    "access_code": grp.access_code,
                    "application": grp.application,
                    "group_name": grp.group_name
                }
                access_groups.append(access_dict)

            data["application_accesses"] = access_groups

            with schema_context("public"):
                user = User.objects.get(pk=access_group_user[0].user_id)
                data["email"] = user.email
                data["first_name"] = user.first_name
                data["last_name"] = user.last_name
                data["last_login"] = user.last_login
            return Response(data)

        except ObjectDoesNotExist:
            raise NotFound(detail="Requested object not found.")

        except Exception as e:
            return Response(
                {"detail": f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



    def get_user_email(self, tenant_user):
        if hasattr(tenant_user, 'user') and hasattr(tenant_user.user, 'email'):
            return tenant_user.user.email
        elif 'email' in self.request.data:
            return self.request.data['email']
        else:
            raise ValueError("No email address available for verification")

    def send_account_email(self, tenant_user, email):
        try:
            email = self.get_user_email(tenant_user)
        except ValueError as e:
            print(f"Error: {str(e)}")
            return
        email_body = f'Your account has been created Successfully, Below are your login credentials\n\n Email: {email} \n Password: {tenant_user.temp_password}'
        email_data = {
            'email_body': email_body,
            'to_email': email,
            'email_subject': 'Account Created Successfully'
        }
        Util.send_email(email_data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant_schema_name = request.auth["schema_name"]
        serializer.validated_data["tenant_schema_name"] = tenant_schema_name
        if 'signature_image' in serializer.validated_data:
            serializer.validated_data["signature"] = convert_to_base64(serializer.validated_data["signature_image"])
        tenant_user, email = serializer.create(serializer.validated_data)
        self.send_account_email(tenant_user, email)
        headers = self.get_success_headers(serializer.validated_data)
        return Response({
            'detail': 'Tenant user created successfully. If an email was provided, account login credentials has been sent.',
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
            email_data = {
                    'email_body': f"Password reset successful, your new password is {new_password}",
                    'to_email': email,
                    'email_subject': 'Passord Reset Successful'
                }
            Util.send_email(email_data)

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
        # # Validate incoming data
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
    
    def get_restructured(self, request):
        """
        Retrieves a restructured dataset of access groups grouped by application.
        This method was implemented to provide a convenient data endpoint for external use cases,
        avoiding the need for additional queries on the client side.
        """
        try:
            applications = AccessGroupRight.objects.values_list('application', flat=True).distinct()
            if not applications:
                return Response({"detail": "No applications found."}, status=status.HTTP_404_NOT_FOUND)

            data = []
            exclude_fields = {'date_created', 'date_updated', 'application'}

            for app in applications:
                access_groups = AccessGroupRight.objects.filter(application=app).distinct('access_code', 'group_name')
                
                if not access_groups.exists():
                    continue  # Skip applications with no access groups

                serialized = AccessGroupRightSerializer(access_groups, many=True)

                cleaned_data = [
                    {k: v for k, v in item.items() if k not in exclude_fields}
                    for item in serialized.data
                ]

                data.append({
                    "application": app,
                    "access_groups": cleaned_data
                })

            payload = {
                "tenant_company_name": request.tenant.company_name,
                "data": data
             }

            return Response(payload, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response(
                {"detail": "Invalid data provided."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except serializers.ValidationError as e:
            return Response(
                {"detail": "An error occurred while serializing the data."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception:
            # Log error here if desired
            return Response(
                {"detail": "An unexpected error occurred while processing the request."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create(self, request, *args, **kwargs):
        serializer = AccessGroupRightSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
  
    
    def partial_update(self, request, access_code=None):
        data = request.data

        group_name = data.get("group_name", None)
        application = data.get("application", None)
        application_module = data.get("application_module", "")

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
                    if action.get("module", None) is None or action.get("rights", None) is None:
                        return Response({"detail": "Both module and rights key must be provided"}, status=status.HTTP_400_BAD_REQUEST)

                    module = action["module"]
                    rights = action["rights"]

                    for right_id in rights:
                        access_group = AccessGroupRight(
                            group_name=group_name.upper().strip(),
                            application=application.lower().strip(),
                            access_code=access_code,
                            application_module=module.lower().strip(),
                            access_right_id=right_id
                        )
                        try:
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
            return Response({"detail": "No access group found with this access code."})
        queryset.delete()
        return Response(
            {"detail": f"Access group deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
# END THE CREATION OF ACCESS GROUP