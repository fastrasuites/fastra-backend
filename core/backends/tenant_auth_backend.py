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
            user = User.objects.get(email=email)
            tenant = Tenant.objects.get(schema_name=schema_name)
            with set_tenant_schema(schema_name):
                tenant_user = TenantUser.objects.get(user_id=user.id, tenant=tenant)
                if tenant_user.check_tenant_password(password):
                    user.backend = 'core.backends.tenant_auth_backend.TenantUserBackend'
                    return user
        except (User.DoesNotExist, Tenant.DoesNotExist, TenantUser.DoesNotExist):
            return None
