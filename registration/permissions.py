from rest_framework.permissions import BasePermission

class IsSuperUserOrTenantAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return user.is_superuser or user.tenantuser_set.filter(role='admin').exists()