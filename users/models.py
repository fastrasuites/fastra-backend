from django.db import models
from django.contrib.auth.models import User
from companies.models import Tenant
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
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='users')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone_number = models.CharField(max_length=20, blank=True)
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='en')
    timezone = models.CharField(max_length=50, choices=TIMEZONE_CHOICES, default='UTC')
    in_app_notifications = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=False)
    signature = models.ImageField(upload_to='signatures', blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.tenant.name} - {self.role}"



class TenantPermission(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='permissions')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.tenant.name} - {self.name}"

class UserPermission(models.Model):
    user = models.ForeignKey(TenantUser, on_delete=models.CASCADE, related_name='permissions')
    permission = models.ForeignKey(TenantPermission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'permission')

    def __str__(self):
        return f"{self.user.user.username} - {self.permission.name}"