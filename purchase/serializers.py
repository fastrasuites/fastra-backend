from django.contrib.auth.models import User
from rest_framework import serializers
from .models import PurchaseRequest, PurchaseRequestItem, Department, Vendor, \
    Product, RequestForQuotation, RequestForQuotationItem, ProductCategory, \
    VendorCategory, UnitOfMeasure, RFQVendorQuote, RFQVendorQuoteItem, \
    PurchaseOrder, PurchaseOrderItem, POVendorQuote, POVendorQuoteItem


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
        queryset=PurchaseRequest.objects.filter(is_hidden=False),
        view_name='purchase-request-detail')
    product = serializers.HyperlinkedRelatedField(
        queryset=Product.objects.filter(is_hidden=False),
        view_name='product-detail')
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = PurchaseRequestItem
        fields = ['id', 'url', 'purchase_request', 'product', 'description', 'qty',
                  'estimated_unit_price', 'total_price']



class PurchaseRequestSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='purchase-request-detail')
    suggested_vendor = serializers.HyperlinkedRelatedField(queryset=Vendor.objects.filter(is_hidden=False),
                                                           view_name='vendor-detail')
    department = serializers.HyperlinkedRelatedField(queryset=Department.objects.filter(is_hidden=False),
                                                     view_name="department-detail")
    items = PurchaseRequestItemSerializer(many=True, read_only=True)
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = PurchaseRequest
        fields = ['url', 'department', 'status', 'date_created', 'date_updated',
                  'purpose', 'suggested_vendor', 'items', 'total_price', 'is_hidden']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        purchase_request = PurchaseRequest.objects.create(**validated_data)
        for item_data in items_data:
            PurchaseRequestItem.objects.create(purchase_request=purchase_request, **item_data)
        return purchase_request

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        instance.date = validated_data.get('date', instance.date)
        instance.requester = validated_data.get('requester', instance.requester)
        instance.department = validated_data.get('department', instance.department)
        instance.status = validated_data.get('status', instance.status)
        instance.purpose = validated_data.get('purpose', instance.purpose)
        instance.suggested_vendor = validated_data.get('suggested_vendor', instance.suggested_vendor)
        instance.save()
        for item_data in items_data:
            PurchaseRequestItem.objects.create(purchase_request=instance, **item_data)
        return instance


class UnitOfMeasureSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='unit-of-measure-detail')

    class Meta:
        model = UnitOfMeasure
        fields = ['url', 'name', 'description', 'created_on', 'is_hidden']


class VendorSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='vendor-detail')
    category = serializers.HyperlinkedRelatedField(
        view_name='vendor-category-detail',
        queryset=VendorCategory.objects.filter(is_hidden=False)
    )

    class Meta:
        model = Vendor
        fields = ['url', 'company_name', 'category', 'email', 'address', 'phone_number', 'is_hidden']


class VendorCategorySerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='vendor-category-detail')
    vendors = VendorSerializer(many=True, read_only=True)

    class Meta:
        model = VendorCategory
        fields = ['url', 'name', 'description', 'vendors', 'is_hidden']
        read_only_fields = ['created_on', 'updated_on']


class ProductSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='product-detail')
    unit_of_measure = UnitOfMeasureSerializer(many=True)
    category = serializers.HyperlinkedRelatedField(
        queryset=ProductCategory.objects.filter(is_hidden=False),
        view_name='product-category-detail')
    company = serializers.HyperlinkedRelatedField(
        queryset=Vendor.objects.filter(is_hidden=False),
        view_name='vendor-detail')

    class Meta:
        model = Product
        fields = ['url', 'name', 'created_on', 'updated_on', 'unit_of_measure', 'type', 'category',
                  'company', 'cost_price', 'selling_price', 'is_hidden']


class ProductCategorySerializer(serializers.HyperlinkedModelSerializer):
    products = ProductSerializer(many=True, read_only=True)
    url = serializers.HyperlinkedIdentityField(view_name='product-category-detail')

    class Meta:
        model = ProductCategory
        fields = ['url', 'name', 'description', 'created_on', 'updated_on', 'products', 'is_hidden']
        read_only_fields = ['created_on', 'updated_on']


class RequestForQuotationItemSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='request-for-quotation-item-detail')
    product = serializers.HyperlinkedRelatedField(queryset=Product.objects.filter(is_hidden=False),
                                                  view_name='product-detail')
    request_for_quotation = serializers.HyperlinkedRelatedField(
        queryset=RequestForQuotation.objects.filter(is_hidden=False),
        view_name='request-for-quotation-detail')
    # This field is a custom property on the model, not a serializer field.
    get_total_price = serializers.ReadOnlyField()

    class Meta:
        model = RequestForQuotationItem
        fields = ['id', 'url', 'request_for_quotation', 'product', 'description',
                  'qty', 'estimated_unit_price', 'get_total_price']


class RequestForQuotationSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='request-for-quotation-detail')
    items = RequestForQuotationItemSerializer(many=True, read_only=True)
    vendor = serializers.HyperlinkedRelatedField(queryset=Vendor.objects.filter(is_hidden=False),
                                                 view_name='vendor-detail')
    rfq_total_price = serializers.ReadOnlyField()

    class Meta:
        model = RequestForQuotation
        fields = ['url', 'expiry_date', 'vendor',
                  'status', 'rfq_total_price', 'items', 'is_hidden']
        read_only_fields = ['date_created', 'date_updated', 'rfq_total_price']


class RFQVendorQuoteItemSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='rfq-vendor-quote-item-detail')
    rfq_vendor_quote = serializers.HyperlinkedRelatedField(
        queryset=RFQVendorQuote.objects.filter(is_hidden=False),
        view_name='rfq-vendor-quote-detail')
    product = serializers.HyperlinkedRelatedField(
        queryset=Product.objects.filter(is_hidden=False),
        view_name='product-detail')
    # This field is a custom property on the model, not a serializer field.
    get_total_price = serializers.ReadOnlyField()

    class Meta:
        model = RFQVendorQuoteItem
        fields = ['id', 'url', 'rfq_vendor_quote', 'product', 'description', 'qty',
                  'estimated_unit_price', 'get_total_price']


class RFQVendorQuoteSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='rfq-vendor-quote-detail')
    items = RFQVendorQuoteItemSerializer(many=True, read_only=True)
    rfq = serializers.HyperlinkedRelatedField(
        queryset=RequestForQuotation.objects.filter(is_hidden=False),
        view_name='request-for-quotation-detail')
    vendor = serializers.HyperlinkedRelatedField(
        queryset=Vendor.objects.filter(is_hidden=False),
        view_name='vendor-detail')
    quote_total_price = serializers.ReadOnlyField()

    class Meta:
        model = RFQVendorQuote
        fields = ['url', 'rfq', 'vendor', 'quote_total_price', 'items', 'is_hidden']
        read_only_fields = ['id', 'quote_total_price']


class PurchaseOrderItemSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='purchase-order-item-detail')
    product = serializers.HyperlinkedRelatedField(
        queryset=Product.objects.filter(is_hidden=False),
        view_name='product-detail')
    purchase_order = serializers.HyperlinkedRelatedField(
        queryset=PurchaseOrder.objects.filter(is_hidden=False),
        view_name='purchase-order-detail')
    # This field is a custom property on the model, not a serializer field.
    get_total_price = serializers.ReadOnlyField()

    class Meta:
        model = PurchaseOrderItem
        fields = ['id', 'url', 'purchase_order', 'product', 'description',
                  'qty', 'estimated_unit_price', 'get_total_price']


class PurchaseOrderSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='purchase-order-detail')
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    vendor = serializers.HyperlinkedRelatedField(
        queryset=Vendor.objects.filter(is_hidden=False),
        view_name='vendor-detail')
    # This field is a custom property on the model, not a serializer field.
    po_total_price = serializers.ReadOnlyField()

    class Meta:
        model = PurchaseOrder
        fields = ['id', 'url', 'status', 'date_created', 'date_updated', 'vendor',
                  'items', 'po_total_price', 'is_hidden']


class POVendorQuoteItemSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='po-vendor-quote-item-detail')
    po_vendor_quote = serializers.HyperlinkedRelatedField(
        queryset=POVendorQuote.objects.filter(is_hidden=False),
        view_name='po-vendor-quote-detail')
    product = serializers.HyperlinkedRelatedField(
        queryset=Product.objects.filter(is_hidden=False),
        view_name='product-detail')
    # This field is a custom property on the model, not a serializer field.
    get_total_price = serializers.ReadOnlyField()

    class Meta:
        model = POVendorQuoteItem
        fields = ['id', 'url', 'po_vendor_quote', 'product', 'description', 'qty',
                  'estimated_unit_price', 'get_total_price']


class POVendorQuoteSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='po-vendor-quote-detail')
    vendor = serializers.HyperlinkedRelatedField(
        queryset=Vendor.objects.filter(is_hidden=False),
        view_name='vendor-detail')
    purchase_order = serializers.HyperlinkedRelatedField(
        queryset=PurchaseOrder.objects.filter(is_hidden=False),
        view_name='purchase-order-detail')
    items = POVendorQuoteItemSerializer(many=True, read_only=True)
    # This field is a custom property on the model, not a serializer field.
    quote_total_price = serializers.ReadOnlyField()

    class Meta:
        model = POVendorQuote
        fields = ['url', 'purchase_order', 'vendor', 'quote_total_price', 'items', 'is_hidden']
