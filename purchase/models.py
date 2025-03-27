from django.core.mail import EmailMessage
from django.db import models
from django.conf import settings

from django.utils import timezone, text
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django_ckeditor_5.fields import CKEditor5Field

import json

from users.models import TenantUser

PURCHASE_REQUEST_STATUS = (
    ('draft', 'Draft'),
    ('approved', 'Approved'),
    ('pending', 'Pending'),
    ('rejected', 'Rejected'),
)

RFQ_STATUS = (
    ('draft', 'Draft'),
    ('approved', 'Approved'),
    ('pending', 'Pending'),
    ('rejected', 'Rejected')
)

PURCHASE_ORDER_STATUS = (
    ('draft', 'Draft'),
    ('awaiting', 'Awaiting Goods'),
    ('completed', 'Order Completed'),
    ('cancelled', 'Cancelled'),
)

PRODUCT_CATEGORY = (
    ('consumable', 'Consumable'),
    ('stockable', 'Stockable'),
    ('service-product', 'Service Product'),
)


# For RFQs
class SelectedVendorManager(models.Manager):
    def get_queryset(self):
        return super(SelectedVendorManager, self).get_queryset().filter(status='selected')


class AwaitingVendorManager(models.Manager):
    def get_queryset(self):
        return super(AwaitingVendorManager, self).get_queryset().filter(status='awaiting')


class CancelledVendorManager(models.Manager):
    def get_queryset(self):
        return super(CancelledVendorManager, self).get_queryset().filter(status='cancelled')


# For Purchase Requests
class DraftPRManager(models.Manager):
    def get_queryset(self):
        return super(DraftPRManager, self).get_queryset().filter(status='draft')


class ApprovedPRManager(models.Manager):
    def get_queryset(self):
        return super(ApprovedPRManager, self).get_queryset().filter(status='approved')


class PendingPRManager(models.Manager):
    def get_queryset(self):
        return super(PendingPRManager, self).get_queryset().filter(status='pending')


class RejectedPRManager(models.Manager):
    def get_queryset(self):
        return super(RejectedPRManager, self).get_queryset().filter(status='rejected')


# For Requests For Quotation (RFQs)
class DraftRFQManager(models.Manager):
    def get_queryset(self):
        return super(DraftRFQManager, self).get_queryset().filter(status='draft')


class ApprovedRFQManager(models.Manager):
    def get_queryset(self):
        return super(ApprovedRFQManager, self).get_queryset().filter(status='approved')


class PendingRFQManager(models.Manager):
    def get_queryset(self):
        return super(PendingRFQManager, self).get_queryset().filter(status='pending')


class RejectedRFQManager(models.Manager):
    def get_queryset(self):
        return super(RejectedRFQManager, self).get_queryset().filter(status='rejected')


# For Purchase Orders
class DraftPOManager(models.Manager):
    def get_queryset(self):
        return super(DraftPOManager, self).get_queryset().filter(status='draft')


class AwaitingPOManager(models.Manager):
    def get_queryset(self):
        return super(AwaitingPOManager, self).get_queryset().filter(status='awaiting')


class CompletedPOManager(models.Manager):
    def get_queryset(self):
        return super(CompletedPOManager, self).get_queryset().filter(status='completed')


class CancelledPOManager(models.Manager):
    def get_queryset(self):
        return super(CancelledPOManager, self).get_queryset().filter(status='cancelled')


# For Active or Hidden States
class ActiveManager(models.Manager):
    def get_queryset(self):
        return super(ActiveManager, self).get_queryset().filter(is_hidden=False)


class HiddenManager(models.Manager):
    def get_queryset(self):
        return super(HiddenManager, self).get_queryset().filter(is_hidden=True)


# To generate unique id for purchase requests
def generate_unique_pr_id():
    last_request = PurchaseRequest.objects.order_by('id').last()
    if last_request:
        last_id = int(last_request.id[2:])
        new_id = f"PR{last_id + 1:06d}"
    else:
        new_id = "PR000001"
    return new_id


# To generate unique id for request for quotations
def generate_unique_rfq_id():
    last_request = RequestForQuotation.objects.order_by('id').last()
    if last_request:
        last_id = int(last_request.id[3:])
        new_id = f"RFQ{last_id + 1:06d}"
    else:
        new_id = "RFQ000001"
    return new_id


# To generate unique id for purchase orders
def generate_unique_po_id():
    last_request = PurchaseOrder.objects.order_by('id').last()
    if last_request:
        last_id = int(last_request.id[2:])
        new_id = f"PO{last_id + 1:06d}"
    else:
        new_id = "PO000001"
    return new_id


class UnitOfMeasure(models.Model):
    unit_name = models.CharField(max_length=100)
    unit_category = models.CharField(max_length=100)
    created_on = models.DateTimeField(auto_now_add=True)
    is_hidden = models.BooleanField(default=False)

    objects = models.Manager()

    class Meta:
        ordering = ['is_hidden', '-created_on']
        verbose_name_plural = 'Units of Measure'

    def __repr__(self):
        return self.unit_name

    def __str__(self):
        return self.unit_name


class Currency(models.Model):
    currency_name = models.CharField(max_length=100)
    currency_symbol = CKEditor5Field(blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)
    is_hidden = models.BooleanField(default=False)

    objects = models.Manager()

    class Meta:
        ordering = ['is_hidden', '-created_on']
        verbose_name_plural = 'Currencies'

    def __str__(self):
        return self.currency_name


class Product(models.Model):
    product_name = models.CharField(max_length=100)
    product_description = CKEditor5Field(null=True, blank=True)
    product_category = models.CharField(max_length=64, choices=PRODUCT_CATEGORY)
    available_product_quantity = models.PositiveIntegerField(verbose_name="Available Product Quantity", default=0)
    total_quantity_purchased = models.PositiveIntegerField(verbose_name="Total Quantity Purchased", default=0)
    unit_of_measure = models.ForeignKey(UnitOfMeasure, on_delete=models.SET_NULL, null=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    is_hidden = models.BooleanField(default=False)

    objects = models.Manager()

    class Meta:
        ordering = ['is_hidden', '-created_on']

    def clean(self):
        valid_categories = [choice[0] for choice in PRODUCT_CATEGORY]  # Extract valid categories
        if text.slugify(self.product_category) not in valid_categories:
            raise ValidationError(
                f"Invalid category '{self.product_category}'. Valid categories are: {', '.join(valid_categories)}.")

    def save(self, *args, **kwargs):
        self.clean()  # Call clean method before saving
        super(Product, self).save(*args, **kwargs)

    def __str__(self):
        return self.product_name


class Department(models.Model):
    name = models.CharField(max_length=100)
    is_hidden = models.BooleanField(default=False)

    objects = models.Manager()

    class Meta:
        ordering = ['is_hidden', '-id']

    def __str__(self):
        return self.name


class Vendor(models.Model):
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    company_name = models.CharField(max_length=200)
    email = models.EmailField(max_length=100)
    address = models.CharField(max_length=300, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='vendor_profiles/', blank=True, null=True)
    is_hidden = models.BooleanField(default=False)

    objects = models.Manager()

    class Meta:
        ordering = ['is_hidden', '-updated_on']

    def __str__(self):
        return self.company_name

    def clean(self):
        if Vendor.objects.filter(company_name=self.company_name).exclude(pk=self.pk).exists():
            raise ValidationError('A vendor with this company name already exists.')
        if Vendor.objects.filter(email=self.email).exclude(pk=self.pk).exists():
            raise ValidationError('A vendor with this email already exists.')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    # Email functionality:
    def send_email(self, subject, message, **kwargs):
        """
        Sends an email to a vendor.
        """
        email = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            to=[self.email]
        )
        email.content_subtype = "html"  # This is necessary to ensure the email is sent as HTML
        email.send()

    @classmethod
    def send_mass_email(cls, subject, message, **kwargs):
        """
        Sends an email to multiple Vendors.
        """
        vendors = cls.objects.all()
        vendor_emails = [vendor.email for vendor in vendors]
        email = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            bcc=vendor_emails,
        )
        email.content_subtype = "html"  # This is necessary to ensure the email is sent as HTML
        email.send()


class PurchaseRequest(models.Model):
    id = models.CharField(max_length=10, primary_key=True, unique=True, default=generate_unique_pr_id, editable=False)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    # requester = models.ForeignKey(TenantUser, on_delete=models.CASCADE, related_name='purchase_requests')
    currency = models.ForeignKey("Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='purchase_requests')
    status = models.CharField(max_length=20, choices=PURCHASE_REQUEST_STATUS, default='draft')
    purpose = CKEditor5Field(blank=True, null=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    is_hidden = models.BooleanField(default=False)
    is_submitted = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=True)

    objects = models.Manager()
    pr_draft = DraftPRManager()
    pr_approved = ApprovedPRManager()
    pr_pending = PendingPRManager()
    pr_rejected = RejectedPRManager()

    @property
    def total_price(self):
        total_price = sum(item.total_price for item in self.items.all())
        return total_price

    class Meta:
        ordering = ['is_hidden', '-date_updated']

    def __str__(self):
        return self.id

    def save(self, *args, **kwargs):
        # If the purchase request is submitted, make it non-editable
        if self.is_submitted:
            self.can_edit = False
        super(PurchaseRequest, self).save(*args, **kwargs)

    def change_status(self, status):
        """Utility method to change the status and save"""
        self.status = status
        self.save()

    def submit(self):
        """Mark the purchase request as pending"""
        self.is_submitted = True
        self.change_status('pending')

    def approve(self):
        """Mark the purchase request as approved"""
        self.is_submitted = True
        self.change_status('approved')

    def reject(self):
        """Mark the purchase request as rejected"""
        self.is_submitted = True
        self.change_status('rejected')


class PurchaseRequestItem(models.Model):
    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name='items')
    date_created = models.DateTimeField(auto_now_add=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    description = models.CharField(max_length=255, null=True, blank=True)
    qty = models.PositiveIntegerField(default=1)
    unit_of_measure = models.ForeignKey("UnitOfMeasure", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="purchase_requests")
    estimated_unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    objects = models.Manager()

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return self.product.product_name


# this is a signal that calculates the qty times the unit price automatically
@receiver(pre_save, sender=PurchaseRequestItem)
def update_total_price(sender, instance, **kwargs):
    instance.total_price = instance.qty * instance.estimated_unit_price


# @receiver(post_save, sender=PurchaseRequest)
# def notify_managers(sender, instance, created, **kwargs):
#     if created or instance.status == 'submitted':
#         managers = User.objects.filter(groups__name='Managers')
#         for manager in managers:
#             send_mail(
#                 'New Purchase Request',
#                 f'A new purchase request {instance.id} has been created/submitted.',
#                 'from@example.com',
#                 [manager.email],
#                 fail_silently=False,
#             )


class RequestForQuotation(models.Model):
    id = models.CharField(max_length=10, primary_key=True, unique=True, default=generate_unique_rfq_id, editable=False)
    purchase_request = models.ForeignKey('PurchaseRequest', on_delete=models.SET_NULL, null=True, blank=True)
    currency = models.ForeignKey("Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='rfqs')
    expiry_date = models.DateTimeField(null=True, blank=True,
                                       help_text="Leave blank for no expiry")
    vendor = models.ForeignKey('Vendor', on_delete=models.CASCADE)
    vendor_category = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=100, choices=RFQ_STATUS, default='draft')

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    is_hidden = models.BooleanField(default=False)

    is_submitted = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=True)

    objects = models.Manager()
    rfq_draft = DraftRFQManager()
    rfq_approved = ApprovedRFQManager()
    rfq_pending = PendingRFQManager()
    rfq_rejected = RejectedRFQManager()

    class Meta:
        ordering = ['is_hidden', '-date_updated']

    def save(self, *args, **kwargs):
        # If the request_for_quotation is submitted, make it non-editable
        if self.is_submitted:
            self.can_edit = False
        super(RequestForQuotation, self).save(*args, **kwargs)

    def change_status(self, status):
        """Utility method to change the status and save"""
        self.status = status
        self.save()

    def submit(self):
        """Mark the request_for_quotation as pending"""
        self.is_submitted = True
        self.change_status('pending')

    def approve(self):
        """Mark the request_for_quotation as approved"""
        self.change_status('approved')

    def reject(self):
        """Mark the request_for_quotation as rejected"""
        self.change_status('rejected')

    def __str__(self):
        return self.id

    @property
    def rfq_total_price(self):
        rfq_total_price = sum(item.total_price for item in self.items.all())
        return rfq_total_price

    @property
    def is_expired(self):
        """Return True if the RFQ has expired based on the expiry_date."""
        if self.expiry_date:
            return timezone.now() > self.expiry_date
        return False

    def send_email(self):
        """
        A function to send an email containing the RFQ to the vendor when a RFQ is created.
        """
        subject = f"Request for Quotation: {self.id}"
        rfq_data = {
            'id': self.id,
            'date_created': self.date_created.strftime('%Y-%m-%d'),
            'date_updated': self.date_updated.strftime('%Y-%m-%d'),
            'expiry_date': self.expiry_date.strftime('%Y-%m-%d') if self.expiry_date else None,
            'vendor': self.vendor.company_name,
            'status': self.status,
            'items': [
                {
                    'product': item.product.product_name,
                    'description': item.product.product_description,
                    'qty': item.qty,
                    'estimated_unit_price': str(item.estimated_unit_price),
                    'actual_unit_price': str(item.actual_unit_price),
                    'total_price': str(item.total_price)
                }
                for item in self.items.all()
            ],
            'rfq_total_price': str(self.rfq_total_price)
        }
        message = json.dumps(rfq_data)
        self.vendor.send_email(subject, message)


class RequestForQuotationItem(models.Model):
    request_for_quotation = models.ForeignKey(RequestForQuotation, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    qty = models.PositiveIntegerField(default=1, verbose_name="QTY")
    unit_of_measure = models.ForeignKey("UnitOfMeasure", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="rfqs")
    estimated_unit_price = models.DecimalField(max_digits=20, decimal_places=2)

    date_created = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()

    def __init__(self, *args, **kwargs):
        self._total_price = None
        super(RequestForQuotationItem, self).__init__(*args, **kwargs)

    def get_total_price(self, *args, **kwargs):
        if self._total_price is None:
            self.set_total_price()
        return self._total_price

    def set_total_price(self, *args, **kwargs):
        self._total_price = self.estimated_unit_price * self.qty

    total_price = property(get_total_price, set_total_price, doc="total price property")

    def __str__(self):
        return self.product.product_name

    class Meta:
        ordering = ['-date_created']


class RFQVendorQuote(models.Model):
    date_opened = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    rfq = models.ForeignKey("RequestForQuotation", on_delete=models.CASCADE, related_name='quotes')
    vendor = models.ForeignKey("Vendor", on_delete=models.CASCADE, related_name='rfq_quotes')
    is_hidden = models.BooleanField(default=False)

    objects = models.Manager()

    @property
    def quote_total_price(self):
        quote_total_price = sum(item.total_price for item in self.items.all())
        return quote_total_price

    class Meta:
        ordering = ['is_hidden', '-date_updated']

    def __str__(self):
        return f"{self.vendor} - {self.rfq}"


class RFQVendorQuoteItem(models.Model):
    rfq_vendor_quote = models.ForeignKey("RFQVendorQuote", on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    description = CKEditor5Field(null=True, blank=True)
    qty = models.PositiveIntegerField(default=1, verbose_name="QTY")
    estimated_unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    objects = models.Manager()

    def __init__(self, *args, **kwargs):
        self._total_price = None
        super(RFQVendorQuoteItem, self).__init__(*args, **kwargs)

    def get_total_price(self, *args, **kwargs):
        if self._total_price is None:
            self.set_total_price()
        return self._total_price

    def set_total_price(self, *args, **kwargs):
        self._total_price = self.estimated_unit_price * self.qty

    total_price = property(get_total_price, set_total_price, doc="total price property")

    def __str__(self):
        return self.product.product_name


class PurchaseOrder(models.Model):
    id = models.CharField(max_length=10, primary_key=True, unique=True, default=generate_unique_po_id, editable=False)
    status = models.CharField(max_length=200, choices=PURCHASE_ORDER_STATUS, default="draft")
    # created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='purchase_orders')
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    vendor = models.ForeignKey("Vendor", on_delete=models.CASCADE, related_name="purchase_orders")
    currency = models.ForeignKey("Currency", on_delete=models.SET_NULL, null=True, related_name='purchase_orders')
    payment_terms = models.CharField(null=True, blank=True)
    purchase_policy = models.CharField(null=True, blank=True)
    delivery_terms = models.CharField(null=True, blank=True)
    is_hidden = models.BooleanField(default=False)

    is_submitted = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=True)

    objects = models.Manager()
    po_draft = DraftPOManager()
    po_awaiting = AwaitingPOManager()
    po_completed = CompletedPOManager()
    po_cancelled = CancelledPOManager()

    class Meta:
        ordering = ['is_hidden', '-date_updated']

    def save(self, *args, **kwargs):
        # If the purchase order is submitted, make it non-editable
        if self.is_submitted:
            self.can_edit = False
        super(PurchaseOrder, self).save(*args, **kwargs)

    def change_status(self, status):
        """Utility method to change the status and save"""
        self.status = status
        self.save()

    def submit(self):
        """Mark the purchase order as pending"""
        self.is_submitted = True
        self.change_status('pending')

    def approve(self):
        """Mark the purchase order as approved"""
        self.change_status('approved')

    def reject(self):
        """Mark the purchase order as rejected"""
        self.change_status('rejected')

    def __str__(self):
        return self.id

    @property
    def po_total_price(self):
        po_total_price = sum(item.total_price for item in self.items.all())
        return po_total_price

    def send_email(self):
        """
        A function to send an email containing the Purchase Order to the vendor when a Purchase Order is created.
        """
        subject = f"Purchase Order: {self.id}"
        po_data = {
            'id': self.id,
            'date_created': self.date_created.strftime('%Y-%m-%d'),
            'date_updated': self.date_updated.strftime('%Y-%m-%d'),
            'status': self.status,
            'vendor': self.vendor.company_name,
            'currency': self.currency.currency_name,
            'payment_terms': self.payment_terms,
            'purchase_policy': self.purchase_policy,
            'delivery_terms': self.delivery_terms,
            'items': [
                {
                    'product': item.product.name,
                    'description': item.description,
                    'qty': item.qty,
                    'estimated_unit_price': str(item.estimated_unit_price),
                    'unit_of_measure': item.unit_of_measure,
                    'total_price': str(item.total_price)
                }
                for item in self.items.all()
            ],
            'po_total_price': str(self.po_total_price)
        }
        message = json.dumps(po_data)
        self.vendor.send_email(subject, message)


class PurchaseOrderItem(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    purchase_order = models.ForeignKey("PurchaseOrder", on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    description = models.CharField(max_length=255, null=True, blank=True)
    qty = models.PositiveIntegerField(default=1, verbose_name="QTY")
    unit_of_measure = models.ForeignKey(UnitOfMeasure, on_delete=models.SET_NULL, null=True,
                                        related_name="purchase_orders")
    estimated_unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    objects = models.Manager()

    class Meta:
        ordering = ['-date_created']

    def __init__(self, *args, **kwargs):
        self._total_price = None
        super(PurchaseOrderItem, self).__init__(*args, **kwargs)

    def get_total_price(self, *args, **kwargs):
        if self._total_price is None:
            self.set_total_price()
        return self._total_price

    def set_total_price(self, *args, **kwargs):
        self._total_price = self.estimated_unit_price * self.qty

    total_price = property(get_total_price, set_total_price, doc="total price property")

    def __str__(self):
        return f"{self.product.product_name} || {self.total_price}"


class POVendorQuote(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    purchase_order = models.ForeignKey("PurchaseOrder", on_delete=models.CASCADE, related_name='quotes')
    vendor = models.ForeignKey("Vendor", on_delete=models.CASCADE, related_name='po_quotes')
    is_hidden = models.BooleanField(default=False)

    objects = models.Manager()

    class Meta:
        ordering = ['is_hidden', '-date_updated']

    def __str__(self):
        return f"{self.vendor} - {self.purchase_order}"

    @property
    def quote_total_price(self):
        quote_total_price = sum(item.total_price for item in self.items.all())
        return quote_total_price


class POVendorQuoteItem(models.Model):
    po_vendor_quote = models.ForeignKey("POVendorQuote", on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    description = CKEditor5Field(null=True, blank=True)
    qty = models.PositiveIntegerField(default=1, verbose_name="QTY")
    estimated_unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    objects = models.Manager()

    def __init__(self, *args, **kwargs):
        self._total_price = None
        super(POVendorQuoteItem, self).__init__(*args, **kwargs)

    def get_total_price(self, *args, **kwargs):
        if self._total_price is None:
            self.set_total_price()
        return self._total_price

    def set_total_price(self, *args, **kwargs):
        self._total_price = self.estimated_unit_price * self.qty

    total_price = property(get_total_price, set_total_price, doc="total price property")

    def __str__(self):
        return self.product.product_name
