from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
from django.utils.translation import gettext_lazy as _
import pytz
from django.contrib.auth.models import User



class Tenant(TenantMixin):
    # Default true, schema will be automatically created and synced when it is saved
    auto_create_schema = True

    # Additional fields based on the image
    schema_name = models.CharField(max_length=255, blank=False, null=False, unique=True)
    company_name = models.CharField(max_length=255, blank=False, null=True, unique=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    paid_until = models.DateField(null=True, blank=True)
    # on_trial = models.BooleanField(default=True)
    # is_verified = models.BooleanField(default=False)

    # user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)


class Domain(DomainMixin):
    pass
