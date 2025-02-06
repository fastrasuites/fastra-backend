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

def binary_search(tenants, target_user_id):
    start = 0
    end = len(tenants) - 1

    while start <= end:
        mid = start + (end - start) // 2

        # Check if the user exists in the current tenant's schema
        with set_tenant_schema(tenants[mid].schema_name):
            try:
                tenant_user = TenantUser.objects.get(user_id=target_user_id, tenant=tenants[mid])
                return tenants[mid]  # Return the tenant if the user is found
            except TenantUser.DoesNotExist:
                pass  # Continue to check the next tenant if the user is not found

        if tenants[mid].id > target_user_id:
            end = mid - 1
        elif tenants[mid].id < target_user_id:
            start = mid + 1
        else:
            return tenants[mid]

    return None  # If no match found


class TenantUserBackend(BaseBackend):
    def authenticate(self, request, email=None, password=None, schema_name=None):
        try:
            user = User.objects.get(email=email)  # Fetch the user
            tenants = Tenant.objects.all().order_by('id')  # Sort tenants by id for binary search

            # Perform binary search to find the tenant
            matched_tenant = binary_search(tenants, user.id)
            print(matched_tenant)

            if matched_tenant:
                with set_tenant_schema(matched_tenant.schema_name):
                    try:
                        tenant_user = TenantUser.objects.get(user_id=user.id, tenant=matched_tenant)
                        if tenant_user.check_tenant_password(password):
                            request.session['tenant_id'] = matched_tenant.id
                            request.session['tenant_schema_name'] = matched_tenant.schema_name
                            request.session['tenant_company_name'] = matched_tenant.company_name
                            user.backend = 'core.backends.tenant_auth_backend.TenantUserBackend'
                            return user
                    except TenantUser.DoesNotExist:
                        return None  # User not found in the matched tenant schema

        except User.DoesNotExist:
            return None  # User not found

        return None  # If no tenant match found, return None
