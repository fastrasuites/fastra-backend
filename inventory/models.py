from django.db import models
from django.core.exceptions import ValidationError
from django.dispatch import receiver
from django.db.models.signals import pre_save, pre_delete

from users.models import TenantUser
from purchase.models import Product

LOCATION_TYPES = (
    ('internal', 'Internal'),
    ('partner', 'Partner'),
)

STOCK_ADJ_STATUS = (
    ('draft', 'Draft'),
    ('done', 'Done')
)

SCRAP_STATUS = (
    ('draft', 'Draft'),
    ('done', 'Done')
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

    objects = models.Manager()

    class Meta:
        ordering = ['is_hidden', '-date_created']

    def __str__(self):
        return self.id

    def __repr__(self):
        return self.id

    def get_active_locations(self):
        multi_location_option = MultiLocation.objects.first().filter(is_activated=True)
        if not multi_location_option and self.objects.all().filter(is_hidden=False).count() >= 3:
            return Location.objects.last()
        return self.objects.all().exclude(location_code__iexact="CUST").exclude(location_code__iexact="SUPP")

    def save(self, *args, **kwargs):
        self.id = f"{self.location_code}{self.id_number:05d}"
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

    def __repr__(self):
        return f"{self.is_activated}"

    def clean(self):
        if not self.pk and MultiLocation.objects.exists():
            raise ValidationError('Only one instance of this model is allowed')

    def save(self, *args, **kwargs):
        self.clean()
        return super(MultiLocation, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Prevent deletion
        raise ValidationError("This instance cannot be deleted")

@receiver(pre_delete, sender=MultiLocation)
def prevent_deletion(sender, instance, **kwargs):
    raise ValidationError("This instance cannot be deleted")


@receiver(pre_save, sender=MultiLocation)
def prevent_multiple_instances(sender, instance, **kwargs):
    if not instance.pk and sender.objects.exists():
        raise ValidationError('Only one instance of MultiLocation Model is allowed')


class StockAdjustment(models.Model):
    adjustment_type = models.CharField(max_length=20, default="Stock Level Update")
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    warehouse_location = models.ForeignKey(Location, on_delete=models.PROTECT)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(choices=STOCK_ADJ_STATUS, max_length=10, default='draft')
    is_done = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=True)
    is_hidden = models.BooleanField(default=False)

    def __str__(self):
        return f"Stock Adjustment - {self.date_created.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        self.warehouse_location = Location.objects.last()
        if self.is_done:
            self.can_edit = False
        super(StockAdjustment, self).save(*args, **kwargs)

    def change_status(self, status):
        """Utility method to change the status and save"""
        self.status = status
        self.save()

    def submit(self):
        """Mark the stock adjustment as draft"""
        self.change_status('draft')

    def final_submit(self):
        self.is_done = True
        self.change_status('done')

    class Meta:
        verbose_name = 'Stock Adjustment'
        verbose_name_plural = 'Stock Adjustments'
        ordering = ['-date_updated', '-date_created']


class StockAdjustmentItem(models.Model):
    stock_adjustment = models.ForeignKey(
        'StockAdjustment',
        on_delete=models.CASCADE,
        related_name='stock_adjustment_items'
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    unit_of_measure = models.CharField(
        max_length=50,
        editable=False,
    )
    current_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
        verbose_name='Current Quantity'
    )
    adjusted_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Adjusted Quantity'
    )

    def __str__(self):
        return f"{self.product.product_name} - {self.adjusted_quantity}"

    def save(self, *args, **kwargs):
        if self.product:
            if not self.unit_of_measure:
                self.unit_of_measure = self.product.unit_of_measure
            if not self.current_quantity:
                self.current_quantity = self.product.available_product_quantity
        else:
            raise ValidationError("Invalid Product")
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Adjustment Line'
        verbose_name_plural = 'Adjustment Lines'


class Scrap(models.Model):
    id = models.CharField(max_length=15, primary_key=True)
    id_number = models.PositiveIntegerField(auto_created=True)
    adjustment_type = models.CharField(max_length=20, default="Stock Level Update")
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    warehouse_location = models.ForeignKey(Location, on_delete=models.PROTECT)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(choices=SCRAP_STATUS, max_length=10, default='draft')
    is_done = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=True)
    is_hidden = models.BooleanField(default=False)

    def __str__(self):
        return f"Scrap - {self.date_created.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        self.id = f"{self.warehouse_location.location_code}IN{self.id_number:05d}"
        self.warehouse_location = Location.objects.last()
        if self.is_done:
            self.can_edit = False
        super(Scrap, self).save(*args, **kwargs)

    def change_status(self, status):
        """Utility method to change the status and save"""
        self.status = status
        self.save()

    def submit(self):
        """Mark the scrap as draft"""
        self.change_status('draft')

    def final_submit(self):
        self.is_done = True
        self.change_status('done')

    class Meta:
        ordering = ['-date_updated', '-date_created']


class ScrapItem(models.Model):
    stock_adjustment = models.ForeignKey(
        'Scrap',
        on_delete=models.CASCADE,
        related_name='scrap_items'
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    scrap_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
        verbose_name='Scrap Quantity'
    )
    adjusted_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Adjusted Quantity'
    )

    def __str__(self):
        return f"{self.product.product_name} - {self.adjusted_quantity}"

    def save(self, *args, **kwargs):
        if self.product:
            if not self.scrap_quantity:
                self.scrap_quantity = self.product.available_product_quantity
        else:
            raise ValidationError("Invalid Product")
        super().save(*args, **kwargs)
