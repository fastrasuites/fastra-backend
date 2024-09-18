from django.shortcuts import render
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, generics, filters
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import Group, Permission, User
from .models import TenantUser
from .serializers import UserSerializer,TenantUserSerializer, GroupSerializer, PermissionSerializer, GroupPermissionSerializer, PasswordChangeSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.sites.shortcuts import get_current_site
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

    @action(detail=True, methods=['post'])
    def add_groups(self, request, pk=None):
        tenant_user = self.get_object()
        groups = Group.objects.filter(id__in=request.data.get('groups', []))
        tenant_user.user.groups.add(*groups)
        return Response({'status': 'Groups added'})

    @action(detail=True, methods=['post'])
    def remove_groups(self, request, pk=None):
        tenant_user = self.get_object()
        groups = Group.objects.filter(id__in=request.data.get('groups', []))
        tenant_user.user.groups.remove(*groups)
        return Response({'status': 'Groups removed'})

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
        
        # Return permission names instead of full objects or IDs
        permission_names = [perm.name for perm in permissions]
        
        return Response({'permissions': permission_names})

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