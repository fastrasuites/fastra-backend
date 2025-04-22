from django.db import models
from django.db.models.signals import pre_save, pre_delete, post_save
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.dispatch import receiver
from django.utils import timezone

from decimal import Decimal

from users.models import TenantUser
from purchase.models import Product

LOCATION_TYPES = (
    ('internal', 'Internal'),
    ('partner', 'Partner'),
)

class InternalLocationManager(models.Manager):
    def get_queryset(self):
        return super(InternalLocationManager, self).get_queryset().filter(location_type="internal")


class PartnerLocationManager(models.Manager):
    def get_queryset(self):
        return super(PartnerLocationManager, self).get_queryset().filter(location_type="partner")


STOCK_ADJ_STATUS = (
    ('draft', 'Draft'),
    ('done', 'Done')
)

class DraftStockAdjManager(models.Manager):
    def get_queryset(self):
        return super(DraftStockAdjManager, self).get_queryset().filter(status="draft")


class DoneStockAdjManager(models.Manager):
    def get_queryset(self):
        return super(DoneStockAdjManager, self).get_queryset().filter(status="done")


SCRAP_STATUS = (
    ('draft', 'Draft'),
    ('done', 'Done')
)


class DraftScrapManager(models.Manager):
    def get_queryset(self):
        return super(DraftScrapManager, self).get_queryset().filter(status="draft")


class DoneScrapManager(models.Manager):
    def get_queryset(self):
        return super(DoneScrapManager, self).get_queryset().filter(status="done")


STOCK_MOVE_STATUS = (
    ('draft', 'Draft'),
    ('pending', 'Pending'),
    ('done', 'Done'),
    ('cancelled', 'Cancelled'),
)


class DraftStockMoveManager(models.Manager):
    def get_queryset(self):
        return super(DraftStockMoveManager, self).get_queryset().filter(status="draft")


class PendingStockMoveManager(models.Manager):
    def get_queryset(self):
        return super(PendingStockMoveManager, self).get_queryset().filter(status="pending")


class DoneStockMoveManager(models.Manager):
    def get_queryset(self):
        return super(DoneStockMoveManager, self).get_queryset().filter(status="done")


class CancelledStockMoveManager(models.Manager):
    def get_queryset(self):
        return super(CancelledStockMoveManager, self).get_queryset().filter(status="cancelled")



STOCK_MOVE_TYPES = [
    ('IN', 'Incoming'),
    ('OUT', 'Outgoing'),
    ('RETURN', 'Return'),
    ('INTERNAL', 'Internal Transfer'),
    ('ADJUSTMENT', 'Inventory Adjustment'),
]

class IncomingStockMoveManager(models.Manager):
    def get_queryset(self):
        return super(IncomingStockMoveManager, self).get_queryset().filter(move_type="IN")

class OutgoingStockMoveManager(models.Manager):
    def get_queryset(self):
        return super(OutgoingStockMoveManager, self).get_queryset().filter(move_type="OUT")

class ReturningStockMoveManager(models.Manager):
    def get_queryset(self):
        return super(ReturningStockMoveManager, self).get_queryset().filter(move_type="RETURN")

class InternalTransferStockMoveManager(models.Manager):
    def get_queryset(self):
        return super(InternalTransferStockMoveManager, self).get_queryset().filter(move_type="INTERNAL")

class InventoryAdjStockMoveManager(models.Manager):
    def get_queryset(self):
        return super(InventoryAdjStockMoveManager, self).get_queryset().filter(move_type="ADJUSTMENT")


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

    internal_locations = InternalLocationManager()
    partner_locations = PartnerLocationManager()

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
        if (MultiLocation.objects.filter(is_activated=False).first()
                and Location.objects.filter(is_hidden=False).count() >= 3):
            raise Exception("Maximum number of locations reached")
        super().save(*args, **kwargs)


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
    id = models.CharField(max_length=15, primary_key=True)
    id_number = models.PositiveIntegerField(auto_created=True)
    adjustment_type = models.CharField(max_length=20, default="Stock Level Update")
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    warehouse_location = models.ForeignKey(Location, on_delete=models.PROTECT)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(choices=STOCK_ADJ_STATUS, max_length=10, default='draft')
    is_done = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=True)
    is_hidden = models.BooleanField(default=False)

    objects = models.Manager()


    def __str__(self):
        return f"Stock Adjustment - {self.date_created.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        self.id = f"{self.warehouse_location.location_code}IN{self.id_number:05d}"
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

    objects = models.Manager()

    def __str__(self):
        return f"Scrap - {self.date_created.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        self.id = f"{self.warehouse_location.location_code}-IN-{self.id_number:05d}"
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
    scrap = models.ForeignKey(
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


class StockMove(models.Model):
    """Records movement of products across different inventory operations"""
    id = models.CharField(max_length=15, primary_key=True)
    id_number = models.PositiveIntegerField(auto_created=True)
    reference = models.CharField(max_length=20, unique=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='stock_moves'
    )
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    move_type = models.CharField(max_length=10, choices=STOCK_MOVE_TYPES)

    # Generic foreign key to link to different inventory record types
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=20)  # Changed from PositiveIntegerField to CharField
    inventory_record = GenericForeignKey('content_type', 'object_id')
    source_document_id = models.CharField(
        max_length=50,
        help_text="Reference number of the source document"
    )

    source_location = models.ForeignKey(
        'Location',
        on_delete=models.PROTECT,
        related_name='source_moves',
        null=True,
        blank=True
    )
    destination_location = models.ForeignKey(
        'Location',
        on_delete=models.PROTECT,
        related_name='destination_moves',
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=STOCK_MOVE_STATUS,
        default='draft'
    )
    date_moved = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Actual date when the stock movement occurred"
    )
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        TenantUser,
        on_delete=models.PROTECT,
        related_name='stock_moves_created'
    )
    moved_by = models.ForeignKey(
        TenantUser,
        on_delete=models.PROTECT,
        related_name='stock_moves_moved',
        null=True,
        blank=True
    )

    objects = models.Manager()

    class Meta:
        ordering = ['-date_created']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['status', 'move_type']),
            models.Index(fields=['date_moved']),
            models.Index(fields=['source_document_id']),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            prefix = f"MOV/{self.move_type}/"
            last_move = StockMove.objects.filter(
                reference__startswith=prefix
            ).order_by('reference').last()

            if last_move:
                last_number = int(last_move.reference.split('/')[1])
                new_number = last_number + 1
            else:
                new_number = 1

            self.reference = f"{prefix}{new_number:06d}"

        super().save(*args, **kwargs)

    def confirm_move(self, user):
        """Confirm the stock movement"""
        self.state = 'done'
        self.date_moved = timezone.now()
        self.moved_by = user
        self.save()


class IncomingInventoryRecordItem(models.Model):
    pass


class OutgoingInventoryRecordItem(models.Model):
    pass


# Signal handler for automatic stock move creation
@receiver(post_save, sender=IncomingInventoryRecordItem)
def create_incoming_stock_move(sender, instance, created, **kwargs):
    """Create stock move when an incoming inventory record item is created"""
    if created:
        StockMove.objects.create(
            product=instance.product,
            unit_of_measure=instance.product.unit_of_measure,
            quantity=instance.quantity,
            move_type='IN',
            inventory_record=instance.incoming_record,  # replace with the appropriate inventory record
            source_document_id=instance.incoming_record_id,  # replace with the appropriate inventory record id
            destination_location=instance.incoming_record.warehouse_location,
            # replace with the appropriate inventory record location
            status='draft',
            created_by=instance.incoming_record.created_by  # replace with the appropriate inventory record creator
        )


@receiver(post_save, sender=OutgoingInventoryRecordItem)
def create_outgoing_stock_move(sender, instance, created, **kwargs):
    """Create stock move when an outgoing inventory record item is created"""
    if created:
        StockMove.objects.create(
            product=instance.product,
            unit_of_measure=instance.product.unit_of_measure,
            quantity=instance.quantity,
            move_type='OUT',
            inventory_record=instance.outgoing_record,  # replace with the appropriate inventory record
            source_document_reference=instance.outgoing_record_id,  # replace with the appropriate inventory record id
            source_location=instance.outgoing_record.warehouse_location,
            # replace with the appropriate inventory record location
            state='draft',
            created_by=instance.delivery.created_by  # replace with the appropriate inventory record creator
        )
