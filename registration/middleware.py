from django_tenants.utils import get_tenant_model, schema_context
from django.http import HttpResponseBadRequest

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split('.')
        if len(host) < 3:  # Ensure there's a subdomain (e.g., tenant.myapp.com)
            return HttpResponseBadRequest("Invalid request: Subdomain required.")

        subdomain = host[0]
        tenant_model = get_tenant_model()

        # Try to fetch tenant based on subdomain
        try:
            tenant = tenant_model.objects.get(schema_name=subdomain)
            request.tenant = tenant
        except tenant_model.DoesNotExist:
            return HttpResponseBadRequest("Tenant not found.")

        # Switch to the correct schema
        with schema_context(tenant.schema_name):
            response = self.get_response(request)

        return response
