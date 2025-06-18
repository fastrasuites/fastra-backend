from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import User, Group
from django_tenants.utils import schema_context

from registration.models import Tenant
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
    role = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, related_name='role', default=None)
    # user = models.ForeignKey(User, on_delete=models.CASCADE, default=None, related_name='tenant_users')
    user_id = models.IntegerField(null=False, unique=True, default=None)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='tenant_users', default=None)
    phone_number = models.CharField(max_length=20, blank=True)
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='en')
    timezone = models.CharField(max_length=50, choices=TIMEZONE_CHOICES, default='UTC')
    in_app_notifications = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    password = models.CharField(max_length=128, blank=True, null=True)

    def set_tenant_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_tenant_password(self, raw_password):
        return check_password(raw_password, self.password)

    @property
    def user(self):
        #return User.objects.using('public').get(id=self.user_id)
        with schema_context('public'):
            return User.objects.get(id=self.user_id)

    def __str__(self):
        return f"{self.user.email} - {self.tenant.company_name} ({self.role.name})"