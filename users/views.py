from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from .models import TenantUser
from .serializers import TenantUserSerializer, PasswordChangeSerializer, GroupSerializer, PermissionSerializer, GroupPermissionSerializer
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.sites.shortcuts import get_current_site
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework import status
from .utils import Util
import jwt
from django.conf import settings
from urllib.parse import urlparse
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework import viewsets, generics


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser, DjangoModelPermissions]

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
        return Response({
            'group': group.id,
            'permissions': [p.id for p in permissions]
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def group_permissions(self, request):
        group_id = request.query_params.get('group_id')
        if not group_id:
            return Response({"error": "group_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            group = Group.objects.get(id=group_id)
        except Group.DoesNotExist:
            return Response({"error": "Group not found"}, status=status.HTTP_404_NOT_FOUND)
        
        permissions = group.permissions.all()
        return Response(PermissionSerializer(permissions, many=True).data)



class TenantUserViewSet(viewsets.ModelViewSet):
    queryset = TenantUser.objects.all()
    serializer_class = TenantUserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TenantUser.objects.all()
    
    def perform_create(self, serializer):
        tenant_user = serializer.save()
        self.send_verification_email(tenant_user)
        

    def get_user_email(self, tenant_user):
        # Attempt to get email from related User model if it exists
        if hasattr(tenant_user, 'user') and hasattr(tenant_user.user, 'email'):
            return tenant_user.user.email
        # If email is passed in the request data, use that
        elif 'email' in self.request.data:
            return self.request.data['email']
        # If no email is available, raise an exception
        else:
            raise ValueError("No email address available for verification")

    def send_verification_email(self, tenant_user):
        try:
            email = self.get_user_email(tenant_user)
        except ValueError as e:
            # Log the error and return without sending email
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
    


    @action(detail=True, methods=['post'])
    def add_groups(self, request, pk=None):
        tenant_user = self.get_object()
        groups = Group.objects.filter(id__in=request.data.get('groups', []))
        tenant_user.user.groups.add(*groups)  # Add groups to additional_groups
        return Response({'status': 'Groups added'})

    @action(detail=True, methods=['post'])
    def remove_groups(self, request, pk=None):
        tenant_user = self.get_object()
        groups = Group.objects.filter(id__in=request.data.get('groups', []))
        tenant_user.user.groups.remove(*groups)  # Remove groups from additional_groups
        return Response({'status': 'Groups removed'})
    
class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PasswordChangeSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



