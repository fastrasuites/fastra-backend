from django.db import models
from django.core.exceptions import ValidationError
from django.dispatch import receiver
from django.db.models.signals import pre_save

from users.models import TenantUser
from purchase.models import Product

LOCATION_TYPES = (
    ('internal', 'Internal'),
    ('partner', 'Partner'),
)


# Create your models here.

class Location(models.Model):
    id = models.CharField(max_length=8, primary_key=True)
    id_number = models.PositiveIntegerField(auto_created=True)
    date_created = models.DateTimeField(auto_created=True)
    location_code = models.CharField(max_length=4, unique=True)
    location_name = models.CharField(max_length=50, unique=True)
    location_type = models.CharField(choices=LOCATION_TYPES, default="internal", max_length=10)
    address = models.CharField(max_length=255, null=True)
    location_manager = models.ForeignKey(
        TenantUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_locations'
    )
    store_keeper = models.ForeignKey(
        TenantUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='store_locations'
    )
    contact_information = models.CharField(max_length=100, null=True, blank=True)
    is_hidden = models.BooleanField(default=False)
    multi_location = models.ForeignKey('MultiLocation', on_delete=models.SET_DEFAULT)

    objects = models.Manager()

    class Meta:
        ordering = ['is_hidden', '-created_on']

    def __str__(self):
        return self.id

    def __repr__(self):
        return self.id

    def save(self, *args, **kwargs):
        self.id = f"{self.location_code}{self.id_number}"
        if (MultiLocation.objects.first().filter(is_activated=False)
                and self.objects.all().filter(is_hidden=False).count() >= 3):
            raise Exception("Maximum number of locations reached")
        super(Location, self).save(*args, **kwargs)


# The multi-location option
class MultiLocation(models.Model):
    is_activated = models.BooleanField(default=False)

    objects = models.Manager()

    def __str__(self):
        return f"{self.is_activated}"

    def save(self, *args, **kwargs):
        if not self.pk and self.objects.exists():
            raise ValidationError('Only one instance of MultiLocation is allowed')
        return super().save(*args, **kwargs)

@receiver(pre_save, sender=MultiLocation)
def prevent_multiple_instances(sender, instance, **kwargs):
    if not instance.pk and sender.objects.exists():
        raise ValidationError('Only one instance of MultiLocation Model is allowed')