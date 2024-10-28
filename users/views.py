import random

from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.core.mail import send_mail

from django_tenants.utils import schema_context
from rest_framework import viewsets, status, generics, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from django_filters.rest_framework import DjangoFilterBackend

from .models import TenantUser
from .serializers import UserLoginSerializer, TenantUserRegisterSerializer, UserDetailsSerializer, \
    ForgotPasswordSerializer, ResetPasswordSerializer

from .utils import Util


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


#
# class UserViewSet(viewsets.ModelViewSet):
#     queryset = User.objects.all()
#     serializer_class = UserSerializer
#
#
# class TenantUserViewSet(SearchDeleteViewSet):
#     queryset = TenantUser.objects.all()
#     serializer_class = TenantUserSerializer
#     permission_classes = [permissions.IsAuthenticated]
#     search_fields = ['user__username', 'user__email']
#
#     def perform_create(self, serializer):
#         tenant_user = serializer.save()
#         self.send_verification_email(tenant_user)
#
#     def get_user_email(self, tenant_user):
#         if hasattr(tenant_user, 'user') and hasattr(tenant_user.user, 'email'):
#             return tenant_user.user.email
#         elif 'email' in self.request.data:
#             return self.request.data['email']
#         else:
#             raise ValueError("No email address available for verification")
#
#     def send_verification_email(self, tenant_user):
#         try:
#             email = self.get_user_email(tenant_user)
#         except ValueError as e:
#             print(f"Error: {str(e)}")
#             return
#
#         token = RefreshToken.for_user(tenant_user)
#         token['email'] = email
#
#         current_site = get_current_site(self.request).domain
#         verification_url = f'https://{current_site}/email-verify?token={str(token.access_token)}'
#
#         email_body = f'Hi {tenant_user.user.username},\nUse the link below to verify your email:\n{verification_url}'
#         email_data = {
#             'email_body': email_body,
#             'to_email': email,
#             'email_subject': 'Verify Your Email'
#         }
#         Util.send_email(email_data)
#
#     def create(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         tenant_user = self.perform_create(serializer)
#         headers = self.get_success_headers(serializer.data)
#         return Response({
#             'detail': 'Tenantuser created successfully. If an email was provided,a verification link has been sent.',
#             'user': serializer.data
#         }, status=status.HTTP_201_CREATED, headers=headers)
#
#
#     def sync_user_permissions(self, user):
#         # Get all permissions from the user's groups
#         group_permissions = Permission.objects.filter(group__user=user).distinct()
#
#         # Add these permissions to the user's direct permissions
#         user.user_permissions.set(group_permissions)
#
#     @action(detail=True, methods=['post'])
#     def add_groups(self, request, pk=None):
#         tenant_user = self.get_object()
#         user = tenant_user.user
#         groups = Group.objects.filter(id__in=request.data.get('groups', []))
#         user.groups.add(*groups)
#         self.sync_user_permissions(user)
#         return Response({'status': 'Groups added and permissions synced'})
#
#     @action(detail=True, methods=['post'])
#     def remove_groups(self, request, pk=None):
#         tenant_user = self.get_object()
#         user = tenant_user.user
#         groups = Group.objects.filter(id__in=request.data.get('groups', []))
#         user.groups.remove(*groups)
#         self.sync_user_permissions(user)
#         return Response({'status': 'Groups removed and permissions synced'})
#
#     def perform_update(self, serializer):
#         tenant_user = serializer.save()
#         self.sync_user_permissions(tenant_user.user)
#
#
#
#     @action(detail=True, methods=['post'])
#     def change_password(self, request, pk=None):
#         tenant_user = self.get_object()
#         serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
#         if serializer.is_valid():
#             user = tenant_user.user
#             user.set_password(serializer.validated_data['new_password'])
#             user.save()
#             return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#
# class GroupViewSet(viewsets.ModelViewSet):
#     queryset = Group.objects.all()
#     serializer_class = GroupSerializer
#     permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
#     search_fields = ['name']
#
# class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
#     queryset = Permission.objects.all()
#     serializer_class = PermissionSerializer
#     permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
#     search_fields = ['name', 'codename']
#
#     def get_queryset(self):
#         app_label = self.request.query_params.get('app', None)
#         if app_label:
#             return Permission.objects.filter(content_type__app_label=app_label)
#         return Permission.objects.all()
#
# class GroupPermissionViewSet(viewsets.ModelViewSet):
#     serializer_class = GroupPermissionSerializer
#     permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
#
#     def get_queryset(self):
#         # Return an empty queryset or implement logic if needed
#         return Group.objects.none()
#
#     def create(self, request):
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         group = serializer.validated_data['group']
#         permissions = serializer.validated_data['permissions']
#         group.permissions.set(permissions)
#
#         # Return permission names instead of IDs
#         permission_names = [perm.name for perm in permissions]
#
#         return Response({
#             'group': group.id,
#             'permissions': permission_names  # Return names instead of IDs
#         }, status=status.HTTP_201_CREATED)
#
#
#
#     # @action(detail=False, methods=['get'])
#     # def group_permissions(self, request):
#     #     group_id = request.query_params.get('group_id')
#     #     if not group_id:
#     #         return Response({"error": "group_id is required"}, status=status.HTTP_400_BAD_REQUEST)
#
#     #     try:
#     #         group = Group.objects.get(id=group_id)
#     #     except Group.DoesNotExist:
#     #         return Response({"error": "Group not found"}, status=status.HTTP_404_NOT_FOUND)
#
#     #     permissions = group.permissions.all()
#
#     #     # Return permission names instead of full objects or IDs
#     #     permission_names = [perm.name for perm in permissions]
#
#     #     return Response({'permissions': permission_names})
#
# class PasswordChangeView(APIView):
#     permission_classes = [permissions.IsAuthenticated]
#     serializer_class = PasswordChangeSerializer
#
#     def post(self, request):
#         serializer = self.serializer_class(data=request.data, context={'request': request})
#         if serializer.is_valid():
#             user = request.user
#             user.set_password(serializer.validated_data['new_password'])
#             user.save()
#             return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginViewSet(viewsets.ViewSet):
    def create(self, request):
        subdomain = request.tenant.schema_name
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        # Authenticate against GlobalUser
        user = authenticate(request, username=email, password=password)
        if user is None:
            return Response({"error": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)

        # Verify tenant-specific role in TenantUser
        with schema_context(subdomain):
            try:
                tenant_user = TenantUser.objects.get(global_user=user, tenant=request.tenant)
            except TenantUser.DoesNotExist:
                return Response({"error": "User does not belong to this tenant."}, status=status.HTTP_403_FORBIDDEN)

        # Generate token
        token, created = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "role": tenant_user.role}, status=status.HTTP_200_OK)


class LogoutViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def create(self, request):
        try:
            request.user.auth_token.delete()  # Delete the token to log out the user
        except Token.DoesNotExist:
            return Response({"error": "Token not found."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)


class RegisterViewSet(viewsets.ViewSet):
    def create(self, request):
        serializer = TenantUserRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        role = serializer.validated_data.get('role', 'viewer')  # Default role

        # Check if GlobalUser already exists
        global_user, created = GlobalUser.objects.get_or_create(
            email=email,
            defaults={'password': make_password(password)}
        )

        # Add user to tenant schema
        with schema_context(request.tenant.schema_name):
            TenantUser.objects.create(
                global_user=global_user,
                tenant=request.tenant,
                role=role
            )

        return Response({"message": "User registered successfully."}, status=status.HTTP_201_CREATED)


class ForgotPasswordViewSet(viewsets.ViewSet):
    def create(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        try:
            user = GlobalUser.objects.get(email=email)
        except GlobalUser.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        # Generate OTP
        otp = random.randint(100000, 999999)
        user.otp = otp
        user.save()

        # Send OTP to user email
        send_mail(
            'Password Reset OTP',
            f'Your OTP for password reset is: {otp}',
            settings.EMAIL_HOST_USER,
            [email],
            fail_silently=False,
        )

        return Response({"message": "OTP sent to your email."}, status=status.HTTP_200_OK)


class ResetPasswordViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def create(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']

        try:
            user = GlobalUser.objects.get(email=email, otp=otp)
        except GlobalUser.DoesNotExist:
            return Response({"error": "Invalid OTP or email."}, status=status.HTTP_400_BAD_REQUEST)

        # Reset password
        user.password = make_password(new_password)
        user.otp = None  # Clear OTP after successful reset
        user.save()

        return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)


class UserDetailsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # Get tenant-specific role
        with schema_context(request.tenant.schema_name):
            tenant_user = TenantUser.objects.get(global_user=request.user, tenant=request.tenant)

        serializer = UserDetailsSerializer({
            "email": request.user.email,
            "role": tenant_user.role,
        })
        return Response(serializer.data, status=status.HTTP_200_OK)
