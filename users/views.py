from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import TenantUser, TenantPermission, UserPermission
from .serializers import TenantUserSerializer, TenantPermissionSerializer, UserPermissionSerializer
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.sites.shortcuts import get_current_site
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework import status
from .utils import Util

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
        verification_url = f'https://{current_site}/companies/email-verify?token={str(token.access_token)}'

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
    
# class TenantUserViewSet(viewsets.ModelViewSet):
#     queryset = TenantUser.objects.all()
#     serializer_class = TenantUserSerializer
#     permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         return TenantUser.objects.all()
    
#     def perform_create(self, serializer):
#         serializer.save()


class TenantPermissionViewSet(viewsets.ModelViewSet):
    queryset = TenantPermission.objects.all()
    serializer_class = TenantPermissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TenantPermission.objects.all()

    def perform_create(self, serializer):
        serializer.save()

class UserPermissionViewSet(viewsets.ModelViewSet):
    queryset = UserPermission.objects.all()
    serializer_class = UserPermissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserPermission.objects.all()