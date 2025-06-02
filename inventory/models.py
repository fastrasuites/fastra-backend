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
from purchase.models import Product, Vendor, PurchaseOrder

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


SCRAP_TYPES = (
    ('damage', 'Damage'),
    ('loss', 'Loss')
)

SCRAP_STATUS = (
    ('draft', 'Draft'),
    ('done', 'Done')
)

class DamageScrapManager(models.Manager):
    def get_queryset(self):
        return super(DamageScrapManager, self).get_queryset().filter(adjustment_type="damage")


class LossScrapManager(models.Manager):
    def get_queryset(self):
        return super(LossScrapManager, self).get_queryset().filter(adjustment_type="loss")


class DraftScrapManager(models.Manager):
    def get_queryset(self):
        return super(DraftScrapManager, self).get_queryset().filter(status="draft")


class DoneScrapManager(models.Manager):
    def get_queryset(self):
        return super(DoneScrapManager, self).get_queryset().filter(status="done")


INCOMING_PRODUCT_RECEIPT_TYPES = (
    ('vendor_receipt', 'Vendor Receipt'),
    ('manufacturing_receipt', 'Manufacturing'),
    ('internal_transfer', 'Internal Transfer'),
    ('returns', 'Returns'),
    ('scrap', 'Scrap')
)


class VendorReceiptIPManager(models.Manager):
    def get_queryset(self):
        return super(VendorReceiptIPManager, self).get_queryset().filter(receipt_type="vendor_receipt")


class ManufacturingIPManager(models.Manager):
    def get_queryset(self):
        return super(ManufacturingIPManager, self).get_queryset().filter(receipt_type="manufacturing")


class InternalTransferIPManager(models.Manager):
    def get_queryset(self):
        return super(InternalTransferIPManager, self).get_queryset().filter(receipt_type="internal_transfer")


class ReturnsIPManager(models.Manager):
    def get_queryset(self):
        return super(ReturnsIPManager, self).get_queryset().filter(receipt_type="returns")


INCOMING_PRODUCT_STATUS = (
    ('draft', 'Draft'),
    ('validated', 'Validated'),
    ('canceled', 'Canceled'),
)


class DraftIncomingProductManager(models.Manager):
    def get_queryset(self):
        return super(DraftIncomingProductManager, self).get_queryset().filter(status="draft")


class ValidatedIncomingProductManager(models.Manager):
    def get_queryset(self):
        return super(ValidatedIncomingProductManager, self).get_queryset().filter(status="validated")


class CanceledIncomingProductManager(models.Manager):
    def get_queryset(self):
        return super(CanceledIncomingProductManager, self).get_queryset().filter(status="canceled")


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
    id = models.CharField(max_length=10, primary_key=True)
    id_number = models.PositiveIntegerField(auto_created=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
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

    @classmethod
    def get_active_locations(cls):
        return cls.objects.all().exclude(location_code__iexact="CUST").exclude(location_code__iexact="SUPP")

    # def save(self, *args, **kwargs):
    #     self.id = f"{self.location_code}{self.id_number:05d}"
    #     if (MultiLocation.objects.filter(is_activated=False).first()
    #             and Location.objects.filter(is_hidden=False).count() >= 3):
    #         raise Exception("Maximum number of locations reached")
    #     super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        # Ensure the location code and location name are unique
        if Location.objects.filter(location_code=self.location_code).exists() or Location.objects.filter(location_name=self.location_name).exists():
            raise ValidationError(f"Location code '{self.location_code}' or Location name '{self.location_name}' "
                                  f"already exists.")
        # Ensure the location type is valid
        if self.location_type not in dict(LOCATION_TYPES).keys():
            raise ValidationError(f"Invalid location type '{self.location_type}'.")
        # Ensure the id is unique
        if self.id and Location.objects.filter(id=self.id).exists():
            raise ValidationError(f"ID '{self.id}' already exists.")
        # Ensure the id_number is auto-incremented based on location_code
        if not self.id_number:
            last_location = Location.objects.filter(location_code=self.location_code).order_by('-id_number').first()
            self.id_number = (last_location.id_number + 1) if last_location else 1
        # Generate the id based on location_code and id_number
        self.id = f"{self.location_code}{self.id_number:05d}"
        # Check the maximum number of locations if MultiLocation is not activated
        if not MultiLocation.objects.first().is_activated and Location.objects.filter(is_hidden=False).count() >= 3:
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
    warehouse_location = models.ForeignKey(
        'Location',
        on_delete=models.PROTECT
    )
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(choices=STOCK_ADJ_STATUS, max_length=10, default='draft')
    is_done = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=True)
    is_hidden = models.BooleanField(default=False)

    objects = models.Manager()

    draft_stock_adjustments = DraftStockAdjManager()
    done_stock_adjustments = DoneStockAdjManager()


    def __str__(self):
        return f"Stock Adjustment - {self.date_created.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        if not self.pk:  # Only perform these checks for new instances
            if self.id and StockAdjustment.objects.filter(id=self.id).exists():
                raise ValidationError(f"ID '{self.id}' already exists.")
            # Ensure the id_number is auto-incremented based on location_code
            if not self.id_number:
                last_stock_adj = StockAdjustment.objects.filter(
                    warehouse_location__location_code=self.warehouse_location.location_code
                ).order_by('-id_number').first()
                self.id_number = (last_stock_adj.id_number + 1) if last_stock_adj else 1
            # Generate the id based on location_code and id_number
            self.id = f"{self.warehouse_location.location_code}ADJ{self.id_number:05d}"
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
    product = models.ForeignKey('purchase.Product', on_delete=models.PROTECT)
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

    objects = models.Manager()

    def __str__(self):
        return f"{self.product.product_name} - {self.adjusted_quantity}"

    def save(self, *args, **kwargs):
        if self.product:
            if not self.unit_of_measure:
                self.unit_of_measure = self.product.unit_of_measure
            if not self.current_quantity:
                self.current_quantity = self.product.available_product_quantity
            if self.adjusted_quantity < 0:
                raise ValidationError("Adjusted quantity cannot be negative")
            if self.stock_adjustment.is_done:
                self.product.available_product_quantity = self.adjusted_quantity
                self.product.save()
        else:
            raise ValidationError("Invalid Product")
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Adjustment Line'
        verbose_name_plural = 'Adjustment Lines'


class Scrap(models.Model):
    id = models.CharField(max_length=15, primary_key=True)
    id_number = models.PositiveIntegerField(auto_created=True)
    adjustment_type = models.CharField(max_length=20, choices=SCRAP_TYPES, default="damage")
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    warehouse_location = models.ForeignKey('Location', on_delete=models.PROTECT)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(choices=SCRAP_STATUS, max_length=10, default='draft')
    is_done = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=True)
    is_hidden = models.BooleanField(default=False)

    objects = models.Manager()

    draft_scraps = DraftScrapManager()
    done_scraps = DoneScrapManager()

    damage_scraps = DamageScrapManager()
    loss_scraps = LossScrapManager()

    def __str__(self):
        return f"Scrap - {self.date_created.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        if not self.pk:  # Only perform these checks for new instances
            if self.id and Scrap.objects.filter(id=self.id).exists():
                raise ValidationError(f"ID '{self.id}' already exists.")
            # Ensure the id_number is auto-incremented based on location_code
            if not self.id_number:
                last_scrap = Scrap.objects.filter(
                    warehouse_location__location_code=self.warehouse_location.location_code
                ).order_by('-id_number').first()
                self.id_number = (last_scrap.id_number + 1) if last_scrap else 1
            # Generate the id based on location_code and id_number
            self.id = f"{self.warehouse_location.location_code}ADJ{self.id_number:05d}"
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
    product = models.ForeignKey('purchase.Product', on_delete=models.PROTECT)
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

    objects = models.Manager()

    def __str__(self):
        return f"{self.product.product_name} - {self.adjusted_quantity}"

    def save(self, *args, **kwargs):
        if self.product:
            if not self.scrap_quantity:
                self.scrap_quantity = self.product.available_product_quantity
            if self.adjusted_quantity < 0:
                raise ValidationError("Adjusted quantity cannot be negative")
            if self.scrap.is_done:
                self.product.available_product_quantity = self.adjusted_quantity
                self.product.save()
        else:
            raise ValidationError("Invalid Product")
        super().save(*args, **kwargs)


class IncomingProduct(models.Model):
    """Records incoming products from suppliers"""
    id = models.CharField(max_length=15, primary_key=True)
    id_number = models.PositiveIntegerField(auto_created=True)
    receipt_type = models.CharField(choices=INCOMING_PRODUCT_RECEIPT_TYPES, default="vendor_receipt")
    backorder_of = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='backorders'
    )
    related_po = models.OneToOneField(
        'purchase.PurchaseOrder',
        related_name='incoming_product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    supplier = models.ForeignKey(
        'purchase.Vendor',
        on_delete=models.PROTECT,
        related_name='incoming_products'
    )
    source_location = models.ForeignKey(
        'Location',
        on_delete=models.PROTECT,
        related_name='incoming_products_from_source',
        default="SUPP00001"
    )
    destination_location = models.ForeignKey(
        'Location',
        on_delete=models.PROTECT,
        related_name='incoming_products_from_destination',
    )
    status = models.CharField(choices=INCOMING_PRODUCT_STATUS, max_length=15, default='draft')
    is_validated = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=True)
    is_hidden = models.BooleanField(default=False)

    objects = models.Manager()

    draft_incoming_products = DraftIncomingProductManager()
    validated_incoming_products = ValidatedIncomingProductManager()
    canceled_incoming_products = CanceledIncomingProductManager()

    vendor_receipt_incoming_products = VendorReceiptIPManager()
    manufacturing_incoming_products = ManufacturingIPManager()
    internal_transfer_incoming_products = InternalTransferIPManager()
    returns_incoming_products = ReturnsIPManager()

    class Meta:
        ordering = ['-date_updated', '-date_created']

    def __str__(self):
        return f"IP_ID: {self.pk:05d}"

    def save(self, *args, **kwargs):
        if not self.pk:  # Only perform these checks for new instances
            if self.id and IncomingProduct.objects.filter(id=self.id).exists():
                raise ValidationError(f"ID '{self.id}' already exists.")
            # Ensure the id_number is auto-incremented based on location_code
            if not self.id_number:
                last_ip = IncomingProduct.objects.filter(
                    source_location__location_code=self.source_location.location_code
                ).order_by('-id_number').first()
                self.id_number = (last_ip.id_number + 1) if last_ip else 1
            # Generate the id based on location_code and id_number
            self.id = f"{self.source_location.location_code}IN{self.id_number:05d}"
        if self.is_validated:
            self.can_edit = False
        super(IncomingProduct, self).save(*args, **kwargs)

    def process_receipt(
            self,
            items_data,
            user_choice={'backorder': False, 'overpay': False}
    ):
        """
        items_data: list of dicts with 'product', 'expected_quantity', 'quantity_received'
        user_choice: dict with keys 'backorder' (True/False), 'overpay' (True/False)
        """
        backorder_items = []
        over_received_items = []
        for item in items_data:
            expected = Decimal(item['expected_quantity'])
            received = Decimal(item['quantity_received'])
            if received == expected:
                continue  # Scenario 1: All good
            elif received < expected:
                # Scenario 2: Less received
                backorder_qty = expected - received
                if user_choice and user_choice.get('backorder'):
                    backorder_items.append({
                        'product': item['product'],
                        'expected_quantity': backorder_qty,
                        'quantity_received': 0,
                    })
                else:
                    # Discard remaining, update expected to received
                    item['expected_quantity'] = received
            else:
                # Scenario 3: More received
                extra_qty = received - expected
                if user_choice and user_choice.get('overpay'):
                    # Adjust expected to received, update cost as needed
                    item['expected_quantity'] = received
                    # You may want to update cost here
                else:
                    # User wants to return extra, set received to expected
                    item['quantity_received'] = expected

        # If backorder is needed, create a new IncomingProduct
        if backorder_items:
            backorder = IncomingProduct.objects.create(
                # copy relevant fields from self
                supplier=self.supplier,
                source_location=self.source_location,
                destination_location=self.destination_location,
                status='draft',
                backorder_of=self,
                # ... other fields ...
            )
            for bo_item in backorder_items:
                IncomingProductItem.objects.create(
                    incoming_product=backorder,
                    product=bo_item['product'],
                    expected_quantity=bo_item['expected_quantity'],
                    quantity_received=0,
                )
            return backorder  # Return the backorder for further processing
        return None


class IncomingProductItem(models.Model):
    incoming_product = models.ForeignKey(
        'IncomingProduct',
        on_delete=models.CASCADE,
        related_name='incoming_product_items'
    )
    product = models.ForeignKey(
        'purchase.Product',
        on_delete=models.PROTECT,
        related_name='incoming_product_items'
    )
    expected_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Expected Quantity',
        default=0
    )
    quantity_received = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Quantity Received',
        default=0
    )

    objects = models.Manager()

    def save(self, *args, **kwargs):
        if self.product:
            related_po = self.incoming_product.related_po
            if related_po:
                # If related_po exists, set expected_quantity from the corresponding PO item
                po_item = related_po.items.filter(product_id=self.product_id).first()
                if po_item:
                    self.expected_quantity = po_item.qty
                else:
                    raise ValidationError("Product not found in related purchase order items.")
            else:
                if not self.expected_quantity:
                    raise ValidationError("Expected quantity is required if there is no related purchase order.")
            if self.expected_quantity < 0 or self.quantity_received < 0:
                raise ValidationError("Quantity cannot be negative")
            if self.incoming_product.is_validated:
                self.product.available_product_quantity += self.expected_quantity
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






# START DELIVERY ORDERS
class DeliveryOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('waiting', 'Waiting'),
        ('ready', 'Ready'),
        ('done', 'Done'),
    ]
    
    order_unique_id = models.CharField(max_length=50, unique=True, editable=False, null=False)
    customer_name = models.CharField(max_length=255, null=False)
    source_location = models.ForeignKey(Location, related_name='source_orders', on_delete=models.PROTECT)
    delivery_address = models.CharField(max_length=255)  # This is the Delivery Address
    date_created = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateField()
    shipping_policy = models.TextField(blank=True, null=True)
    return_policy = models.TextField(blank=True, null=True)
    assigned_to = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    is_hidden = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.order_unique_id} - {self.customer_name}"
    
    def save(self, *args, **kwargs):
        for field in self._meta.fields:
            value = getattr(self, field.name)
            if isinstance(value, str):
                setattr(self, field.name, value.strip())
        super().save(*args, **kwargs)
        

    
class DeliveryOrderItem(models.Model):
    delivery_order = models.ForeignKey(DeliveryOrder, on_delete=models.CASCADE, related_name='delivery_order_items')
    product_item = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_items')
    quantity_to_deliver = models.PositiveIntegerField()
    is_available = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product_item.product_name} ({self.quantity_to_deliver} {self.product_item.unit_of_measure})"
    
    def save(self, *args, **kwargs):
        for field in self._meta.fields:
            value = getattr(self, field.name)
            if isinstance(value, str):
                setattr(self, field.name, value.strip())
        super().save(*args, **kwargs)
# END DELIVERY ORDERS



# START RETURNED PRODUCTS
class DeliveryOrderReturn(models.Model):
    source_document = models.OneToOneField(DeliveryOrder, on_delete=models.CASCADE, related_name='source_document') #This is referencing the delivery order
    unique_record_id = models.CharField(max_length=50, unique=True, editable=False, null=False, blank=False)
    date_of_return = models.DateField(default=timezone.now)
    source_location = models.ForeignKey(Location, related_name='source_delivery_location', on_delete=models.PROTECT) # In this case, this is the location of the Customer
    return_warehouse_location = models.ForeignKey('Location', related_name='return_warehouse', on_delete=models.PROTECT)
    reason_for_return = models.TextField()
    status = models.CharField(max_length=10, default='waiting')
    date_created = models.DateTimeField(auto_now_add=True)
    is_hidden = models.BooleanField(default=False)

    def __str__(self):
        return f"Return {self.unique_record_id} for Order {self.source_document.order_unique_id}"
    
    def save(self, *args, **kwargs):
        for field in self._meta.fields:
            value = getattr(self, field.name)
            if isinstance(value, str):
                setattr(self, field.name, value.strip())
        super().save(*args, **kwargs)
    

class DeliveryOrderReturnItem(models.Model):
    delivery_order_return = models.ForeignKey(DeliveryOrderReturn, on_delete=models.CASCADE, related_name='delivery_order_return_items')
    returned_product_item = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='returned_product_items')
    initial_quantity = models.PositiveIntegerField()
    returned_quantity = models.PositiveIntegerField(default=0)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.returned_product_item.product_name} ({self.returned_quantity} {self.returned_product_item.unit_of_measure})"
    
    def save(self, *args, **kwargs):
        for field in self._meta.fields:
            value = getattr(self, field.name)
            if isinstance(value, str):
                setattr(self, field.name, value.strip())
        super().save(*args, **kwargs)
# END RETURNED PRODUCTS


# START RETURN OF INCOMING PRODUCTS
class ReturnIncomingProduct(models.Model):
    unique_id = models.CharField(max_length=50, primary_key=True, unique=True, editable=False, null=False)
    source_document = models.OneToOneField(IncomingProduct, on_delete=models.CASCADE, related_name="return_incoming_product")
    reason_for_return = models.TextField()
    returned_date = models.DateField(auto_now_add=False)
    is_approved = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    date_approved = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.unique_id


class ReturnIncomingProductItem(models.Model):
    return_incoming_product = models.ForeignKey(ReturnIncomingProduct, 
                                                on_delete=models.CASCADE, related_name="return_incoming_product_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="return_product_items")
    quantity_to_be_returned = models.PositiveIntegerField(null=False)
    quantity_received = models.PositiveIntegerField(null=False)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.return_incoming_product.unique_id} {self.product.product_name}"
# END RETURN OF INCOMING PRODUCTS

