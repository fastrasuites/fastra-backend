from django.db import models
import pytz
from django.contrib.auth.models import User
from django.utils import timezone
import random
from registration.models import Tenant, UserProfile

from django.db.models.signals import post_save
from django.dispatch import receiver

CURRENCY_CHOICES = [
    ('NGN', 'Nigerian Naira'),
    ('USD', 'US Dollar'),
    ('EUR', 'Euro'),
    ('GBP', 'British Pound'),
    # Add more currency choices as needed
]

LANGUAGE_CHOICES = [
    ('en', 'English'),
    ('es', 'Spanish'),
    ('fr', 'French'),
    # Add more language choices as needed
]

TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.all_timezones]





@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


class CompanyProfile(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE)
    logo = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    street_address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    registration_number = models.CharField(max_length=100, blank=True, null=True)
    tax_id = models.CharField(max_length=100, blank=True, null=True)
    currency = models.CharField(max_length=20, choices=CURRENCY_CHOICES, default='NGN', null=False)
    industry = models.CharField(max_length=100, blank=True, null=True)
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='en', null=False)
    company_size = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(max_length=255, blank=True, null=True)


class CompanyRole(models.Model):
    name = models.CharField(max_length=100)
    company = models.ForeignKey('CompanyProfile', related_name='roles', on_delete=models.CASCADE)

    def __str__(self):
        return self.name

"""class CompanyProfile(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE)
    logo = models.ImageField(upload_to='company_logo', blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    registration_number = models.CharField(max_length=100, blank=True, null=True)
    tax_id = models.CharField(max_length=100, blank=True, null=True)
    currency = models.CharField(max_length=20, choices=CURRENCY_CHOICES, default='NGN', null=False)
    industry = models.CharField(max_length=100, blank=True, null=True)
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='en', null=False)
    time_zone = models.CharField(max_length=50, choices=TIMEZONE_CHOICES, default='UTC', null=False)
    """


"""class OTP(models.Model):
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
        """