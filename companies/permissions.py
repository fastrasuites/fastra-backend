from rest_framework import permissions
from django_tenants.utils import get_tenant

class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow the admin user of a tenant to make changes.
    """

    def has_permission(self, request, view):
        # Get the current tenant
        tenant = get_tenant(request)
        
        # Check if the current user is the admin (first user) of the tenant
        return request.user.is_authenticated and request.user == tenant.user