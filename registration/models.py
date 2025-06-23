from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import User
from django.utils import timezone
import random
from django.contrib.auth.models import Group


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
    is_verified = models.BooleanField(default=False)


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
    
class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=4)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = str(random.randint(1000, 9999))
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=5)
        return super().save(*args, **kwargs)

    def is_valid(self):
        return timezone.now() <= self.expires_at and not self.is_used


class Application(models.Model):
    name = models.CharField(max_length=20, null=False)   
    is_hidden = models.BooleanField(default=False) 
    date_updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        for field in self._meta.fields:
            value = getattr(self, field.name)
            if isinstance(value, str):
                setattr(self, field.name, value.strip().upper())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Application Module: {self.name}"


class ApplicationModule(models.Model):
    name = models.CharField(max_length=20, null=False)   
    application = models.ForeignKey(Application, on_delete=models.CASCADE, null=True, related_name="application_modules")
    is_hidden = models.BooleanField(default=False) 
    date_updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        for field in self._meta.fields:
            value = getattr(self, field.name)
            if isinstance(value, str):
                setattr(self, field.name, value.strip().upper())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Application Module: {self.name}"


class AccessRight(models.Model):
    name = models.CharField(max_length=20, null=False)    
    is_hidden = models.BooleanField(default=False) 
    date_updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        for field in self._meta.fields:
            value = getattr(self, field.name)
            if isinstance(value, str):
                setattr(self, field.name, value.strip().lower())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Access Right: {self.name}"
    


