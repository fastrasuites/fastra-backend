from django.contrib.auth.models import User
from django.utils.text import slugify
from rest_framework import serializers

from users.models import TenantUser
from inventory.models import Location
from .models import (PurchaseRequest, PurchaseRequestItem, Department, Vendor,
                     Product, RequestForQuotation, RequestForQuotationItem, UnitOfMeasure,
                     PurchaseOrder, PurchaseOrderItem, PRODUCT_CATEGORY, Currency)


# Switched to HyperlinkedIdentityField, HyperlinkedRelatedField for hyperlink support
# Switched to HyperlinkedModelSerializer for dynamic field selection
# The url field is used to link to the detail view of the model in the API response

class UserSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='user-detail')

    class Meta:
        model = User
        fields = ['id', 'url', 'username', 'email', 'first_name', 'last_name']


class DepartmentSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="department-detail")

    class Meta:
        model = Department
        fields = ['url', 'name', 'is_hidden']


class PurchaseRequestItemSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='purchase-request-item-detail')
    purchase_request = serializers.HyperlinkedRelatedField(
        # queryset=PurchaseRequest.objects.filter(is_hidden=False),
        view_name='purchase-request-detail', read_only=True)
    product = serializers.HyperlinkedRelatedField(
        queryset=Product.objects.filter(is_hidden=False),
        view_name='product-detail')
    unit_of_measure = serializers.HyperlinkedRelatedField(
        queryset=UnitOfMeasure.objects.filter(is_hidden=False),
        view_name='unit-of-measure-detail'
    )
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = PurchaseRequestItem
        fields = ['id', 'url', 'purchase_request', 'product', 'description', 'qty', 'unit_of_measure',
                  'estimated_unit_price', 'total_price']


class PurchaseRequestSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='purchase-request-detail')
    # requester = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)
    currency = serializers.HyperlinkedRelatedField(queryset=Currency.objects.filter(is_hidden=False),
                                                   view_name='currency-detail')
    vendor = serializers.HyperlinkedRelatedField(queryset=Vendor.objects.filter(is_hidden=False),
                                                 view_name='vendor-detail')
    requesting_location = serializers.PrimaryKeyRelatedField(
        many=False,
        queryset=Location.objects.filter(is_hidden=False),
        allow_null=True
    )
    items = PurchaseRequestItemSerializer(many=True, allow_empty=False)
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = PurchaseRequest
        fields = ['url', 'id', 'status', 'date_created', 'date_updated', 'currency', 'requesting_location',
                  'purpose', 'vendor', 'items', 'total_price', 'can_edit', 'is_submitted', 'is_hidden']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        if not items_data:
            raise serializers.ValidationError("At least one item is required to create a purchase request.")
        purchase_request = PurchaseRequest.objects.create(**validated_data)
        for item_data in items_data:
            PurchaseRequestItem.objects.create(purchase_request=purchase_request, **item_data)
        return purchase_request

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        # instance.date_updated = validated_data.get('date_updated', instance.date_updated)
        instance.currency = validated_data.get('currency', instance.currency)
        instance.purpose = validated_data.get('purpose', instance.purpose)
        instance.vendor = validated_data.get('vendor', instance.vendor)
        instance.status = validated_data.get('status', instance.status)
        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                PurchaseRequestItem.objects.update_or_create(id=item_data.get('id'),
                                                             purchase_request=instance,
                                                             defaults=item_data)
        return instance


class UnitOfMeasureSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='unit-of-measure-detail')

    class Meta:
        model = UnitOfMeasure
        fields = ['url', 'unit_name', 'unit_symbol', 'unit_category', 'created_on', 'is_hidden']


class CurrencySerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='currency-detail')

    class Meta:
        model = Currency
        fields = ['url', 'id', 'currency_name', 'currency_code', 'currency_symbol', 'created_on', 'is_hidden']


class ExcelUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    check_for_duplicates = serializers.BooleanField(default=False)  # Adding this field to the serializer


class VendorSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='vendor-detail')
    profile_picture = serializers.ImageField(required=False)

    class Meta:
        model = Vendor
        fields = ['url', 'id', 'company_name', 'profile_picture', 'email', 'address', 'phone_number', 'is_hidden']

    def validate(self, data):
        if Vendor.objects.filter(company_name=data['company_name']).exclude(
                pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError('A vendor with this company name already exists.')
        if Vendor.objects.filter(email=data['email']).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError('A vendor with this email already exists.')
        return data


class ProductSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='product-detail')
    check_for_duplicates = serializers.BooleanField(write_only=True, required=False,
                                                    help_text="Mark if you want to update existing products.\n It "
                                                              "will check by name and category.  ")
    unit_of_measure = serializers.HyperlinkedRelatedField(
        queryset=UnitOfMeasure.objects.filter(is_hidden=False),
        view_name='unit-of-measure-detail')
    unit_of_measure_details = UnitOfMeasureSerializer(read_only=True, source='unit_of_measure')
    class Meta:
        model = Product
        fields = ['url', 'id', 'product_name', 'product_description', 'product_category',
                  'available_product_quantity', 'total_quantity_purchased', 'unit_of_measure',
                  'created_on', 'updated_on', 'is_hidden', 'check_for_duplicates', 'unit_of_measure_details']

    # Check if the product_category is among the options available
    def validate_product_category(self, value):
        valid_categories = [choice[0] for choice in PRODUCT_CATEGORY]  # Extract the valid category keys
        if slugify(value) not in valid_categories:
            raise serializers.ValidationError(
                f"Invalid category '{value}'. Valid categories are: {', '.join(valid_categories)}.")
        return value

    def create(self, validated_data):
        check_for_duplicates = validated_data.pop('check_for_duplicates', False)

        if check_for_duplicates:
            # Check for duplicate product by name
            product_name = validated_data.get('product_name')
            product_category = slugify(validated_data.get('product_category'))
            existing_product = Product.objects.filter(product_name__iexact=product_name,
                                                      product_category__iexact=product_category).first()

            if existing_product:
                # Update existing product quantities
                existing_product.product_description = validated_data['product_description']
                existing_product.unit_of_measure = validated_data['unit_of_measure']
                existing_product.available_product_quantity += validated_data['available_product_quantity']
                existing_product.total_quantity_purchased += validated_data['total_quantity_purchased']
                existing_product.save()
                return existing_product

        # If not checking for duplicates, create a new product
        return super().create(validated_data)


class RequestForQuotationItemSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='request-for-quotation-item-detail')
    product = serializers.HyperlinkedRelatedField(queryset=Product.objects.filter(is_hidden=False),
                                                  view_name='product-detail')
    unit_of_measure = serializers.HyperlinkedRelatedField(queryset=UnitOfMeasure.objects.filter(is_hidden=False),
                                                          view_name='unit-of-measure-detail')
    request_for_quotation = serializers.HyperlinkedRelatedField(view_name='request-for-quotation-detail',
                                                                read_only=True)
    # This field is a custom property on the model, not a serializer field.
    get_total_price = serializers.ReadOnlyField()

    class Meta:
        model = RequestForQuotationItem
        fields = ['id', 'url', 'request_for_quotation', 'product', 'description',
                  'qty', 'unit_of_measure', 'estimated_unit_price', 'get_total_price']


class RequestForQuotationSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='request-for-quotation-detail')
    purchase_request = serializers.PrimaryKeyRelatedField(
        many=False,
        queryset=PurchaseRequest.objects.filter(is_hidden=False, status='approved')
    )
    currency = serializers.HyperlinkedRelatedField(queryset=Currency.objects.filter(is_hidden=False),
                                                   view_name='currency-detail')
    vendor = serializers.HyperlinkedRelatedField(queryset=Vendor.objects.filter(is_hidden=False),
                                                 view_name='vendor-detail')
    rfq_total_price = serializers.ReadOnlyField()
    items = RequestForQuotationItemSerializer(many=True)

    class Meta:
        model = RequestForQuotation
        fields = ['url', 'id', 'expiry_date', 'vendor', 'purchase_request', 'currency',
                  'status', 'rfq_total_price', 'items', 'is_hidden', 'is_expired', 'is_submitted', 'can_edit']
        read_only_fields = ['date_created', 'date_updated', 'rfq_total_price']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        if not items_data:
            raise serializers.ValidationError("At least one item is required to create a RFQ.")
        if validated_data['purchase_request'].status != 'approved':
            raise serializers.ValidationError("The purchase request must be approved before creating a RFQ.")
        rfq = RequestForQuotation.objects.create(**validated_data)
        for item_data in items_data:
            RequestForQuotationItem.objects.create(request_for_quotation=rfq, **item_data)
        return rfq

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        # instance.date_updated = validated_data.get('date_updated', instance.date_updated)
        instance.expiry_date = validated_data.get('expiry_date', instance.expiry_date)
        instance.vendor = validated_data.get('vendor', instance.vendor)
        instance.vendor_category = validated_data.get('vendor_category', instance.vendor_category)
        instance.purchase_request = validated_data.get('purchase_request', instance.purchase_request)
        instance.currency = validated_data.get('currency', instance.currency)
        instance.status = validated_data.get('status', instance.status)
        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                RequestForQuotationItem.objects.update_or_create(id=item_data.get('id'),
                                                                 request_for_quotation=instance,
                                                                 defaults=item_data)
        return instance


# class RFQVendorQuoteItemSerializer(serializers.HyperlinkedModelSerializer):
#     url = serializers.HyperlinkedIdentityField(view_name='rfq-vendor-quote-item-detail')
#     rfq_vendor_quote = serializers.HyperlinkedRelatedField(
#         view_name='rfq-vendor-quote-detail', read_only=True)
#     product = serializers.HyperlinkedRelatedField(
#         queryset=Product.objects.filter(is_hidden=False),
#         view_name='product-detail')
#     # This field is a custom property on the model, not a serializer field.
#     get_total_price = serializers.ReadOnlyField()
#
#     class Meta:
#         model = RFQVendorQuoteItem
#         fields = ['id', 'url', 'rfq_vendor_quote', 'product', 'description', 'qty',
#                   'estimated_unit_price', 'get_total_price']
#
#
# class RFQVendorQuoteSerializer(serializers.HyperlinkedModelSerializer):
#     url = serializers.HyperlinkedIdentityField(view_name='rfq-vendor-quote-detail')
#     items = RFQVendorQuoteItemSerializer(many=True)
#     rfq = serializers.HyperlinkedRelatedField(
#         queryset=RequestForQuotation.objects.filter(is_hidden=False),
#         view_name='request-for-quotation-detail')
#     vendor = serializers.HyperlinkedRelatedField(
#         queryset=Vendor.objects.filter(is_hidden=False),
#         view_name='vendor-detail')
#     quote_total_price = serializers.ReadOnlyField()
#
#     class Meta:
#         model = RFQVendorQuote
#         fields = ['url', 'id', 'rfq', 'vendor', 'quote_total_price', 'items', 'is_hidden']
#         read_only_fields = ['id', 'quote_total_price']
#
#     def create(self, validated_data):
#         items_data = validated_data.pop('items')
#         if not items_data:
#             raise serializers.ValidationError("At least one item is required to create a RFQ vendor quote.")
#         rfq_vendor_quote = RFQVendorQuote.objects.create(**validated_data)
#         for item_data in items_data:
#             RFQVendorQuoteItem.objects.create(rfq_vendor_quote=rfq_vendor_quote, **item_data)
#         return rfq_vendor_quote
#
#     def update(self, instance, validated_data):
#         items_data = validated_data.pop('items', None)
#         instance.rfq = validated_data.get('rfq', instance.rfq)
#         instance.vendor = validated_data.get('vendor', instance.vendor)
#         instance.save()
#
#         if items_data is not None:
#             instance.items.all().delete()
#             for item_data in items_data:
#                 RFQVendorQuoteItem.objects.update_or_create(id=item_data.get('id'),
#                                                             rfq_vendor_quote=instance,
#                                                             defaults=item_data)
#         return instance


class PurchaseOrderItemSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='purchase-order-item-detail')
    product = serializers.HyperlinkedRelatedField(
        queryset=Product.objects.filter(is_hidden=False),
        view_name='product-detail')
    purchase_order = serializers.HyperlinkedRelatedField(
        view_name='purchase-order-detail', read_only=True, lookup_field='id')
    unit_of_measure = serializers.HyperlinkedRelatedField(
        queryset=UnitOfMeasure.objects.filter(is_hidden=False),
        view_name='unit-of-measure-detail')
    # This field is a custom property on the model, not a serializer field.
    get_total_price = serializers.ReadOnlyField()

    class Meta:
        model = PurchaseOrderItem
        fields = ['id', 'url', 'purchase_order', 'product', 'description',
                  'qty', 'unit_of_measure', 'estimated_unit_price', 'get_total_price']


class PurchaseOrderSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='purchase-order-detail', lookup_field='id',
                                               lookup_url_kwarg='id')
    # created_by = serializers.HyperlinkedRelatedField(
    #     queryset=User.objects.filter(username__icontains='admin'),
    #     view_name='user-detail')
    items = PurchaseOrderItemSerializer(many=True)
    # add a one-to-one serializer field
    related_rfq = serializers.PrimaryKeyRelatedField(
        many=False,
        queryset=RequestForQuotation.objects.filter(is_hidden=False, status='approved'),
        allow_null=True
    )
    destination_location = serializers.PrimaryKeyRelatedField(
        many=False,
        queryset=Location.objects.filter(is_hidden=False),
        allow_null=True
    )
    vendor = serializers.HyperlinkedRelatedField(
        queryset=Vendor.objects.filter(is_hidden=False),
        view_name='vendor-detail')
    currency = serializers.HyperlinkedRelatedField(
        queryset=Currency.objects.filter(is_hidden=False),
        view_name='currency-detail')
    # This field is a custom property on the model, not a serializer field.
    po_total_price = serializers.ReadOnlyField()

    class Meta:
        model = PurchaseOrder
        fields = ['id', 'url', 'status', 'date_created', 'date_updated', 'related_rfq', 'vendor', 'currency',
                  'payment_terms', 'destination_location', 'purchase_policy', 'delivery_terms',
                  'items', 'po_total_price', 'is_hidden', 'is_submitted', 'can_edit']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        if not items_data:
            raise serializers.ValidationError("At least one item is required to create a purchase order.")
        po = PurchaseOrder.objects.create(**validated_data)
        for item_data in items_data:
            PurchaseOrderItem.objects.create(purchase_order=po, **item_data)
        return po

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        # instance.date_updated = validated_data.get('date_updated', instance.date_updated)
        # instance.created_by = validated_data.get('created_by', instance.created_by)
        instance.vendor = validated_data.get('vendor', instance.vendor)
        instance.destination_location = validated_data.get('destination_location', instance.destination_location)
        instance.payment_terms = validated_data.get('payment_terms', instance.payment_terms)
        instance.purchase_policy = validated_data.get('purchase_policy', instance.purchase_policy)
        instance.delivery_terms = validated_data.get('delivery_terms', instance.delivery_terms)
        instance.currency = validated_data.get('currency', instance.currency)
        instance.status = validated_data.get('status', instance.status)
        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                PurchaseOrderItem.objects.update_or_create(id=item_data.get('id'),
                                                           purchase_order=instance,
                                                           defaults=item_data)
        return instance


# class POVendorQuoteItemSerializer(serializers.HyperlinkedModelSerializer):
#     url = serializers.HyperlinkedIdentityField(view_name='po-vendor-quote-item-detail')
#     po_vendor_quote = serializers.HyperlinkedRelatedField(
#         view_name='po-vendor-quote-detail', read_only=True)
#     product = serializers.HyperlinkedRelatedField(
#         queryset=Product.objects.filter(is_hidden=False),
#         view_name='product-detail')
#     # This field is a custom property on the model, not a serializer field.
#     get_total_price = serializers.ReadOnlyField()
#
#     class Meta:
#         model = POVendorQuoteItem
#         fields = ['id', 'url', 'po_vendor_quote', 'product', 'description', 'qty',
#                   'estimated_unit_price', 'get_total_price']
#
#
# class POVendorQuoteSerializer(serializers.HyperlinkedModelSerializer):
#     url = serializers.HyperlinkedIdentityField(view_name='po-vendor-quote-detail')
#     vendor = serializers.HyperlinkedRelatedField(
#         queryset=Vendor.objects.filter(is_hidden=False),
#         view_name='vendor-detail')
#     purchase_order = serializers.HyperlinkedRelatedField(
#         queryset=PurchaseOrder.objects.filter(is_hidden=False),
#         view_name='purchase-order-detail')
#     items = POVendorQuoteItemSerializer(many=True)
#     # This field is a custom property on the model, not a serializer field.
#     quote_total_price = serializers.ReadOnlyField()
#
#     class Meta:
#         model = POVendorQuote
#         fields = ['url', 'id', 'purchase_order', 'vendor', 'quote_total_price', 'items', 'is_hidden']
#
#     def create(self, validated_data):
#         items_data = validated_data.pop('items')
#         if not items_data:
#             raise serializers.ValidationError("At least one item is required to create a PO vendor quote.")
#         po_vendor_quote = POVendorQuote.objects.create(**validated_data)
#         for item_data in items_data:
#             POVendorQuoteItem.objects.create(po_vendor_quote=po_vendor_quote, **item_data)
#         return po_vendor_quote
#
#     def update(self, instance, validated_data):
#         items_data = validated_data.pop('items', None)
#         instance.purchase_order = validated_data.get('purchase_order', instance.purchase_order)
#         instance.vendor = validated_data.get('vendor', instance.vendor)
#         instance.save()
#
#         if items_data is not None:
#             instance.items.all().delete()
#             for item_data in items_data:
#                 POVendorQuoteItem.objects.update_or_create(id=item_data.get('id'),
#                                                            po_vendor_quote=instance,
#                                                            defaults=item_data)
#         return instance
