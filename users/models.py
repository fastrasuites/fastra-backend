from django.db import models

from registration.models import Tenant, GlobalUser
import pytz

LANGUAGE_CHOICES = [
    ('en', 'English'),
    ('es', 'Spanish'),
    ('fr', 'French'),
    # Add more language choices as needed
]

TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.all_timezones]

ROLE_CHOICES = [
    ('admin', 'Administrator'),
    ('accountant', 'Accountant'),
    ('manager', 'Manager'),
    ('hr', 'HR'),
    ('sales', 'Sales'),
    ('employee', 'Employee'),
    # Add more roles as needed
]


class TenantUser(models.Model):
    global_user = models.ForeignKey(GlobalUser, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    role = models.CharField(max_length=20,
                            choices=ROLE_CHOICES)

    class Meta:
        unique_together = ('global_user', 'tenant')

