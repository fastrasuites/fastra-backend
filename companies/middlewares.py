# from django.utils.deprecation import MiddlewareMixin
# from django_tenants.utils import get_tenant_model, get_public_schema_name
# from django.db import connection
# from .models import Domain  # Import your Domain model
import logging

from django.db import connection
from django.urls import get_resolver, resolve
from django.urls.resolvers import RegexPattern
from django_tenants.middleware.main import TenantMainMiddleware

from core.errors.exceptions import TenantNotFoundException
from registration.models import Tenant
from registration.utils import set_tenant_schema
from rest_framework_simplejwt.authentication import JWTAuthentication

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

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

        # Dynamically fetch public URLs from urls_public
        # public_urlpatterns = get_resolver('urls_public').url_patterns
        public_urlpatterns = get_resolver('core.urls_public').url_patterns
        self.public_routes = [
            pattern.pattern.regex.pattern if isinstance(pattern.pattern, RegexPattern)
            else pattern.pattern._route
            for pattern in public_urlpatterns
        ]

    def __call__(self, request):
        # Check if the request is for a public route
        print("ROUTE", self.public_routes, request.path)
        if any(request.path.startswith(f"/{route}") for route in self.public_routes):
            print("STARTS WITH")
            return self.get_response(request)

        # Proceed with tenant resolution for tenant-specific routes
        full_host = request.get_host().split(':')[0]
        schema_name = full_host.split('.')[0]
        print("NOT HERE")
        try:
            tenant = Tenant.objects.get(schema_name=schema_name)
        except Tenant.DoesNotExist:
            raise TenantNotFoundException()

        with set_tenant_schema(schema_name):
            request.tenant = tenant
            response = self.get_response(request)

        return response




class TenantJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        resolved_url = resolve(request.path)
        public_routes = ['registration', 'register', 'schema', 'swagger-ui']
        if resolved_url.view_name in public_routes:
            with set_tenant_schema('public'):
                return None

        full_host = request._request.get_host().split(':')[0]
        schema_name = full_host.split('.')[0]
        try:
            tenant = Tenant.objects.get(schema_name=schema_name)
        except Tenant.DoesNotExist:
            raise TenantNotFoundException()

        with set_tenant_schema('public'):
            auth_header = request.headers.get('Authorization')

            if not auth_header:
                return None

            # raw_token = self.get_raw_token(auth_header)
            raw_token = auth_header.split(' ')[1]
            if raw_token is None:
                return None

            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
            return (user, validated_token)

class DebugTenantMainMiddleware(TenantMainMiddleware):
    def process_request(self, request):
        print(f"Starting TenantMainMiddleware with hostname: {request.get_host()}")
        super().process_request(request)
        print(f"Schema set to: {connection.schema_name}")