from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User

from registration.models import Tenant
from registration.utils import set_tenant_schema
from users.models import TenantUser


# class TenantUserBackend(BaseBackend):
#     def authenticate(self, request, email=None, password=None, schema_name=None):
#         try:
#             user = User.objects.get(email=email)
#             tenant = Tenant.objects.get(schema_name=schema_name)
#             with set_tenant_schema(schema_name):
#                 tenant_user = TenantUser.objects.get(user_id=user.id, tenant=tenant)
#                 if tenant_user.check_tenant_password(password):
#                     return user
#         except (User.DoesNotExist, Tenant.DoesNotExist, TenantUser.DoesNotExist):
#             return None
#
#     def get_user(self, user_id):
#         try:
#             return User.objects.get(pk=user_id)
#         except User.DoesNotExist:
#             return None

class TenantUserBackend(BaseBackend):
    def authenticate(self, request, email=None, password=None, schema_name=None):
        try:
            user = User.objects.get(email=email)  # Fetch the user first
        except User.DoesNotExist:
            return None  # If user doesn't exist, return None immediately

        try:
            tenant_user = TenantUser.objects.get(user_id=user.id)
            with set_tenant_schema(tenant_user.tenant.schema_name):
                if tenant_user.check_tenant_password(password):
                    request.session['tenant_id'] = tenant_user.tenant.id
                    request.session['tenant_schema_name'] = tenant_user.tenant.schema_name
                    request.session['tenant_company_name'] = tenant_user.tenant.company_name
                    user.backend = 'core.backends.tenant_auth_backend.TenantUserBackend'
                    return user
        except TenantUser.DoesNotExist:
            return None  # If no matching tenant found, return None

        return None  # If no matching tenant found, return None
