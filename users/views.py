from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import TenantUser, TenantPermission, UserPermission
from .serializers import TenantUserSerializer, TenantPermissionSerializer, UserPermissionSerializer
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response


class TenantUserViewSet(viewsets.ModelViewSet):
    queryset = TenantUser.objects.all()
    serializer_class = TenantUserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TenantUser.objects.all()
    
    def perform_create(self, serializer):
        serializer.save()


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