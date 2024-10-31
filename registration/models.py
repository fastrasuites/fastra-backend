from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import User
from django.utils import timezone



class Tenant(TenantMixin):
    """
       Tenant model representing a company or organization.
    """
    auto_create_schema = True

    schema_name = models.CharField(max_length=255, blank=False, null=False, unique=True)
    company_name = models.CharField(max_length=255, blank=False, null=True, unique=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    paid_until = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="tenants")
    otp = models.CharField(max_length=255, null=True)
    otp_requested_at = models.DateTimeField(null=False, default=timezone.now)
    otp_verified_at = models.DateTimeField(null=True)
    is_verified = models.BooleanField(default=False, null=False, blank=False)


class Domain(DomainMixin):
    """
    Domain model representing the tenant's domain.
    """
    pass




class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_verified = models.BooleanField(default=False)
    allow_multiple_tenants = models.BooleanField(default=False)
    max_tenants = models.PositiveIntegerField(null=True, blank=True, default=1)

    def __str__(self):
        return f"{self.user.username}'s Profile"