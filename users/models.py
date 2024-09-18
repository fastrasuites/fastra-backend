from django.db import models
from django.contrib.auth.models import User, Group
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
    role = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, related_name='role')
    phone_number = models.CharField(max_length=20, blank=True)
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='en')
    timezone = models.CharField(max_length=50, choices=TIMEZONE_CHOICES, default='UTC')
    in_app_notifications = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=False)
    # signature = models.ImageField(upload_to='signatures', blank=True, null=True)
    is_hidden = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username} - {self.role}"



