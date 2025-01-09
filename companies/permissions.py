from rest_framework import permissions
from rest_framework.permissions import IsAdminUser
from users.models import TenantUser

class HasTenantAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        try:
            TenantUser.objects.get(
                user_id=request.user.id,
                tenant=request.tenant
            )
            return True
        except TenantUser.DoesNotExist:
            return False