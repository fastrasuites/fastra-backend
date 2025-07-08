from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import User, Group
from django_tenants.utils import schema_context

from companies.models import CompanyRole
from registration.models import AccessRight, Tenant
import pytz
from django.db import connection

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
    company_role = models.ForeignKey(CompanyRole, on_delete=models.SET_NULL, null=True, default=None, related_name='company_tenant_user_role')
    user_id = models.IntegerField(null=False, unique=True, default=None)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='tenant_users', default=None)
    phone_number = models.CharField(max_length=20, blank=True)
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='en')
    timezone = models.CharField(max_length=50, choices=TIMEZONE_CHOICES, default='UTC')
    in_app_notifications = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    password = models.CharField(max_length=128, blank=True, null=True)
    temp_password = models.CharField(max_length=128, blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True, blank=True, null=True)
    signature = models.TextField(null=True, default=None, blank=True)
    user_image = models.TextField(null=True, default=None, blank=True)

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
    


#THIS IS HERE BECAUSE EACH TENANT CAN DETERMINE THEIR VARIOUS ACCESS GROUP NAMES AND IT IS DYNAMIC WITH THE COMPANY STRUCTURE
class AccessGroupRight(models.Model):
    access_code = models.CharField(max_length=20, null=False)
    application = models.CharField(max_length=50, null=True)
    application_module = models.CharField(max_length=50, null=True)
    group_name = models.CharField(max_length=20, null=False)
    access_right = models.ForeignKey(AccessRight, on_delete=models.CASCADE)
    is_hidden =  models.BooleanField(default=False)
    date_updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def save(self, *args, **kwargs):        
        if self.application:
            self.application = self.application.lower()
        if self.application_module:
            self.application_module = self.application_module.lower()
        super().save(*args, **kwargs)

    @classmethod
    def get_next_id(cls):
        with connection.cursor() as cursor:
            # Use the correct sequence name for the current tenant's schema
            cursor.execute("SELECT nextval('users_accessgroupright_id_seq')")
            next_id = cursor.fetchone()[0]
        return next_id

    def __str__(self):
        return f"Group Name: {self.group_name}"
    


class AccessGroupRightUser(models.Model):
    access_code = models.CharField(max_length=20, null=True, blank=True)
    user_id = models.BigIntegerField(null=True, blank=True)
    is_hidden =  models.BooleanField(default=False)
    date_updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.access_code} - {self.user_id}"