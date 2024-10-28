from django.db import models
from django.conf import settings
from django.utils import timezone

from django_tenants.models import TenantMixin, DomainMixin

import random

class Tenant(TenantMixin):
    # Default true, schema will be automatically created and synced when it is saved
    auto_create_schema = True

    # Additional fields based on the image
    schema_name = models.CharField(max_length=255, blank=False, null=False, unique=True)
    company_name = models.CharField(max_length=255, blank=False, null=True, unique=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)
    paid_until = models.DateField(null=True, blank=True)


class Domain(DomainMixin):
    pass


class GlobalUser(models.Model):
    pass


class TenantCreationOTP(models.Model):
    email = models.EmailField()  # Email associated with tenant creation
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def generate_otp(self):
        """Generate a random 6-digit OTP"""
        self.otp = f"{random.randint(100000, 999999)}"
        self.save()

    def is_expired(self):
        """Check if OTP is expired (e.g., after 10 minutes)"""
        expiration_time = self.created_at + timezone.timedelta(minutes=10)
        return timezone.now() > expiration_time

    def __str__(self):
        return f"OTP for {self.email}"