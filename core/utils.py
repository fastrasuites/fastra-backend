from django_tenants.utils import schema_context


def enforce_tenant_schema(view_func):
    def wrapped_view(self, request, *args, **kwargs):
        with schema_context(request.tenant.schema_name):
            return view_func(self, request, *args, **kwargs)
    return wrapped_view