from rest_framework.exceptions import ValidationError

class TenantNotFoundException(ValidationError):
    default_detail = "Tenant does not exist"
    default_code = "tenant_not_found"

class InvalidCredentialsException(ValidationError):
    default_detail = "Invalid credentials."
    default_code = "invalid_credentials"
