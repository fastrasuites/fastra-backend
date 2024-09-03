# from rest_framework import viewsets
# from rest_framework.permissions import IsAuthenticated
# from .models import TenantUser, TenantPermission, UserPermission
# from .serializers import TenantUserSerializer, TenantPermissionSerializer, UserPermissionSerializer

# class TenantUserViewSet(viewsets.ModelViewSet):
#     queryset = TenantUser.objects.all()
#     serializer_class = TenantUserSerializer
#     # permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         return TenantUser.objects.filter(tenant=self.request.tenant)

#     def perform_create(self, serializer):
#         serializer.save(tenant=self.request.tenant)

# class TenantPermissionViewSet(viewsets.ModelViewSet):
#     queryset = TenantPermission.objects.all()
#     serializer_class = TenantPermissionSerializer
#     # permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         return TenantPermission.objects.filter(tenant=self.request.tenant)

#     def perform_create(self, serializer):
#         serializer.save(tenant=self.request.tenant)

# class UserPermissionViewSet(viewsets.ModelViewSet):
#     queryset = UserPermission.objects.all()
#     serializer_class = UserPermissionSerializer
#     # permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         return UserPermission.objects.filter(user__tenant=self.request.tenant)