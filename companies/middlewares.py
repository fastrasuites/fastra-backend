from django_tenants.utils import schema_context
from django.db import connection
from django.urls import get_resolver, resolve
from django.urls.resolvers import RegexPattern
from django_tenants.middleware.main import TenantMainMiddleware
from rest_framework.response import Response
from rest_framework import status

from core.errors.exceptions import TenantNotFoundException
from registration.models import Tenant
from users.models import TenantUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import User

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        public_urlpatterns = get_resolver('core.urls_public').url_patterns
        self.public_routes = [
            pattern.pattern.regex.pattern if isinstance(pattern.pattern, RegexPattern)
            else pattern.pattern._route
            for pattern in public_urlpatterns
        ]

    def __call__(self, request):
        # Check if the request is for a public route
        if any(request.path.startswith(f"/{route}") for route in self.public_routes):
            connection.set_schema_to_public()
            return self.get_response(request)

        # Get tenant from hostname
        full_host = request.get_host().split(':')[0]
        schema_name = full_host.split('.')[0]

        try:
            tenant = Tenant.objects.get(schema_name=schema_name)
            connection.set_tenant(tenant)
            request.tenant = tenant

            # Check if user is authenticated and belongs to the tenant
            if request.user.is_authenticated:
                with schema_context(schema_name):
                    try:
                        TenantUser.objects.get(user_id=request.user.id, tenant=tenant)
                    except TenantUser.DoesNotExist:
                        return Response(
                            {"error": "You don't have access to this tenant"},
                            status=status.HTTP_403_FORBIDDEN
                        )

            response = self.get_response(request)
            return response

        except Tenant.DoesNotExist:
            raise TenantNotFoundException()




class TenantJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        print("Starting authentication process...")
        header = self.get_header(request)
        if header is None:
            print("No auth header found")
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            print("No raw token found")
            return None

        print(f"Raw token: {raw_token}")
        validated_token = self.get_validated_token(raw_token)
        if validated_token is None:
            print("Token validation failed")
            return None

        user = self.get_user(validated_token)
        if user is None:
            print("User not found")
            return None

        # Get tenant from request
        full_host = request.get_host().split(':')[0]
        schema_name = full_host.split('.')[0]
        connection.set_schema(schema_name)

        try:
            tenant = Tenant.objects.get(schema_name=schema_name)
            tenant_user = TenantUser.objects.get(user_id=user.id, tenant=tenant)
            return (user, validated_token)
        except Tenant.DoesNotExist:
            print("Tenant does not exist.")
            return None
        except TenantUser.DoesNotExist:
            print("Tenant user does not exist.")
            return None
        except Exception as e:
            print(f"Authentication error: {str(e)}")
            return None

    def get_user(self, validated_token):
        try:
            user_id = validated_token['user_id']
            print(f"Extracted user_id from token: {user_id}")

            # Set the schema to public before querying the User model
            connection.set_schema_to_public()
            
            user = User.objects.get(id=user_id)
            print(f"Found user: {user.username}")
            return user
        except (User.DoesNotExist, KeyError):
            print(f"User with id {user_id} does not exist")
            return None
        finally:
            # Optionally reset to the previous schema if needed
            print(f"Resetting schema to: {connection.schema_name}")
            # connection.set_schema(previous_schema_name)  # Uncomment if you want to reset

class DebugTenantMainMiddleware(TenantMainMiddleware):
    def process_request(self, request):
        print(f"Starting TenantMainMiddleware with hostname: {request.get_host()}")
        super().process_request(request)
        print(f"Schema set to: {connection.schema_name}")