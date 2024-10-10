# from django.utils.deprecation import MiddlewareMixin
# from django_tenants.utils import get_tenant_model, get_public_schema_name
# from django.db import connection
# from .models import Domain  # Import your Domain model

# class TenantMiddleware(MiddlewareMixin):
#     def process_request(self, request):
#         hostname = request.get_host().split(':')[0]
#         TenantModel = get_tenant_model()

#         try:
#             # Find the domain associated with the hostname
#             domain = Domain.objects.get(domain=hostname)
#             tenant = domain.tenant
#             connection.set_schema(tenant.schema_name)
#             request.tenant = tenant
#         except Domain.DoesNotExist:
#             connection.set_schema(get_public_schema_name())
#             request.tenant = None



# from django_tenants.middleware import BaseTenantMiddleware
# from django_tenants.utils import get_tenant_model, get_public_schema_name
# from django.db import connection

# class TenantMiddleware(BaseTenantMiddleware):
#     def get_tenant(self, request):
#         hostname = request.get_host().split(':')[0]
#         TenantModel = get_tenant_model()
#         try:
#             return TenantModel.objects.get(domain__domain=hostname)
#         except TenantModel.DoesNotExist:
#             return None

#     def process_request(self, request):
#         tenant = self.get_tenant(request)
#         if tenant:
#             connection.set_schema(tenant.schema_name)
#             request.tenant = tenant
#         else:
#             connection.set_schema(get_public_schema_name())



# from django_tenants.utils import schema_context
# from django.utils.deprecation import MiddlewareMixin
# from .models import Domain

# class TenantMiddleware(MiddlewareMixin):
#     def process_request(self, request):
#         domain = request.get_host().split(':')[0]  # Extract domain, handling ports if present
#         tenant = None

#         try:
#             domain_instance = Domain.objects.get(domain=domain)
#             tenant = domain_instance.tenant
#         except Domain.DoesNotExist:
#             tenant = None

#         if tenant:
#             schema_name = tenant.schema_name
#             request.tenant = tenant
#             request.schema_name = schema_name
#         else:
#             request.tenant = None
#             request.schema_name = None

#     def process_response(self, request, response):
#         schema_context(None)
#         return response
