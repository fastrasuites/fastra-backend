from drf_spectacular.extensions import OpenApiAuthenticationExtension

class TenantJWTAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = 'companies.middlewares.TenantJWTAuthentication'  # Full import path
    name = 'TenantJWTAuthentication'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        }