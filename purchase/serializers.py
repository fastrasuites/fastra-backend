from django.contrib.auth.models import User
from django.utils.text import slugify
from rest_framework import serializers

from shared.serializers import LocationSerializer
from users.models import TenantUser
from inventory.models import Location, MultiLocation
from users.serializers import TenantUserSerializer
from .models import (PurchaseRequest, PurchaseRequestItem, Department, Vendor,
                     Product, RequestForQuotation, RequestForQuotationItem, UnitOfMeasure,
                     PurchaseOrder, PurchaseOrderItem, PRODUCT_CATEGORY, Currency)


# Switched to HyperlinkedIdentityField, HyperlinkedRelatedField for hyperlink support
# Switched to HyperlinkedModelSerializer for dynamic field selection
# The url field is used to link to the detail view of the model in the API response
class UnitOfMeasureSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='unit-of-measure-detail')
    unit_symbol = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = UnitOfMeasure
        fields = ['url', 'unit_name', 'unit_symbol', 'unit_category', 'created_on', 'is_hidden']


class CurrencySerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='currency-detail')
    currency_symbol = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Currency
        fields = ['url', 'id', 'currency_name', 'currency_code', 'currency_symbol', 'created_on', 'is_hidden']


class ExcelUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    check_for_duplicates = serializers.BooleanField(default=False)  # Adding this field to the serializer


class VendorSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='vendor-detail')
    profile_picture_image = serializers.ImageField(required=False, write_only=True, allow_null=True)

    class Meta:
        model = Vendor
        fields = [
            'url', 'id', 'company_name', 'profile_picture', 'profile_picture_image', 'email', 'address',
            'phone_number', 'is_hidden'
        ]
        extra_kwargs = {'profile_picture': {'read_only': True}}

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
    unit_of_measure = serializers.PrimaryKeyRelatedField(
        queryset=UnitOfMeasure.objects.filter(is_hidden=False),
    )
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

    def validate(self, attrs):
        if attrs['product_category'] is not None:
            self.validate_product_category(attrs.get('product_category'))
        # Check if product_name and product_category combination already exists
        if Product.objects.filter(
            product_name__iexact=attrs['product_name'],
            product_category__iexact=slugify(attrs['product_category'])
        ).exclude(
            pk=self.instance.pk if self.instance else None
        ).exists():
            raise serializers.ValidationError('A product with this name and category already exists.')
        return attrs

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


class PurchaseRequestItemSerializer(serializers.ModelSerializer):
    purchase_request = serializers.PrimaryKeyRelatedField(read_only=True)
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_hidden=False),
    )
    unit_of_measure = serializers.PrimaryKeyRelatedField(
        queryset=UnitOfMeasure.objects.filter(is_hidden=False),
        required=False,
        allow_null=True,
        allow_empty=True
    )
    total_price = serializers.ReadOnlyField()
    product_details = ProductSerializer(read_only=True, source='product')

    class Meta:
        model = PurchaseRequestItem
        fields = ['id', 'purchase_request', 'product', 'product_details', 'description', 'qty', 'unit_of_measure',
                  'estimated_unit_price', 'total_price']

    def validate(self, data):
        if data.get('qty') is None or data['qty'] <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return data

    def create(self, validated_data):
        if not validated_data.get('description'):
            validated_data['description'] = validated_data['product'].product_description
        if not validated_data.get('unit_of_measure'):
            validated_data['unit_of_measure'] = validated_data['product'].unit_of_measure
        return super().create(validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            if attr != 'id':
                setattr(instance, attr, value)
        if not instance.description:
            instance.description = instance.product.product_description
        if not instance.unit_of_measure:
            instance.unit_of_measure = instance.product.unit_of_measure
        instance.save()
        return instance


class PurchaseRequestSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='purchase-request-detail')
    requester = serializers.PrimaryKeyRelatedField(
        required=False,
        queryset=TenantUser.objects.filter(is_hidden=False)
    )
    currency = serializers.PrimaryKeyRelatedField(
        queryset=Currency.objects.filter(is_hidden=False)
    )
    vendor = serializers.PrimaryKeyRelatedField(
        queryset=Vendor.objects.filter(is_hidden=False)
    )
    requesting_location = serializers.PrimaryKeyRelatedField(
        queryset=Location.get_active_locations().filter(is_hidden=False)
    )
    currency_details = CurrencySerializer(source='currency', read_only=True)
    requesting_location_details = LocationSerializer(source='requesting_location', read_only=True)
    vendor_details = VendorSerializer(source='vendor', read_only=True)
    items = PurchaseRequestItemSerializer(many=True, allow_empty=False)
    requester_details = TenantUserSerializer(source='requester', read_only=True)
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = PurchaseRequest
        fields = [
            'url', 'id', 'status', 'date_created', 'date_updated', 'currency', 'requester', 'requester_details',
            'requesting_location', 'purpose', 'vendor', 'items', 'total_price', 'can_edit',
            'is_submitted', 'is_hidden', 'requesting_location_details', 'currency_details', 'vendor_details'
        ]

    def to_internal_value(self, data):
        data = data.copy()
        if 'requester' not in data or not data.get('requester'):
            user = self.context['request'].user
            try:
                tenant_user = TenantUser.objects.get(user_id=user.id, is_hidden=False)
                data['requester'] = tenant_user.pk
            except TenantUser.DoesNotExist:
                raise serializers.ValidationError({'requester': 'Logged in user is not a valid tenant member.'})
        return super().to_internal_value(data)

    def validate_create(self, data):
        required_fields = ['items', 'requester', 'currency', 'vendor']
        for field in required_fields:
            if not data.get(field):
                raise serializers.ValidationError(f"{field.replace('_', ' ').capitalize()} is required to create a purchase request.")
        if data.get('requesting_location') is None and not MultiLocation.objects.filter(is_activated=False).exists():
            raise serializers.ValidationError("Requesting location is required when multi-location is activated.")
        if PurchaseRequest.objects.filter(
                requester=data.get('requester'),
                requesting_location=data.get('requesting_location'),
                purpose=data.get('purpose'),
                vendor=data.get('vendor'),
                status__in=['draft', 'pending'],
                currency=data.get('currency'),
                items__product__in=[item['product'] for item in data.get('items', [])],
                is_hidden=False
        ).exists():
            raise serializers.ValidationError("A purchase request with these details already exists.")
        items_data = data.get('items', [])
        # avoid duplicate products in items
        incoming_product_ids = [
            item['product'].id if hasattr(item['product'], 'id') else int(item['product'])
            for item in items_data if 'product' in item
        ]
        if self.instance:
            existing_product_ids = [
                item.product.id for item in self.instance.items.all()
            ]
        else:
            existing_product_ids = []
        all_product_ids = incoming_product_ids + existing_product_ids
        if len(all_product_ids) != len(set(all_product_ids)):
            raise serializers.ValidationError("Duplicate products found in items. Each product should be unique.")
        return data

    def validate_update(self, data):
        if 'items' in data:
            items = data['items']
            if not items:
                raise serializers.ValidationError("At least one item is required for a partial update.")
            incoming_product_ids = [
                item['product'].id if hasattr(item['product'], 'id') else int(item['product'])
                for item in items if 'product' in item
            ]
            # Only check for duplicates in incoming items, not combined with existing
            if len(incoming_product_ids) != len(set(incoming_product_ids)):
                raise serializers.ValidationError("Duplicate products found in items. Each product should be unique.")
        required_fields = ['requesting_location', 'requester', 'currency', 'vendor']
        for field in required_fields:
            if field in data and data[field] is None:
                raise serializers.ValidationError(f"{field.replace('_', ' ').capitalize()} is required.")
        if 'requesting_location' in data and data['requesting_location'] is None and not MultiLocation.objects.filter(is_activated=False).exists():
            raise serializers.ValidationError("Requesting location is required when multi-location is activated.")
        return data

    def validate(self, data):
        if self.instance is None:
            self.validate_create(data)
        else:
            self.validate_update(data)
        return data

    def create(self, validated_data):
        if not validated_data.get('requesting_location') and MultiLocation.objects.filter(is_activated=False).exists():
            validated_data['requesting_location'] = Location.get_active_locations().first()
        items_data = validated_data.pop('items', [])
        purchase_request = PurchaseRequest.objects.create(**validated_data)
        # use bulk_create for efficiency
        PurchaseRequestItem.objects.bulk_create(
            [PurchaseRequestItem(
                purchase_request=purchase_request,
                **item_data
            ) for item_data in items_data])
        return purchase_request

    def update(self, instance, validated_data):
        partial = self.context.get('partial', False)
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            # If partial, handle only provided fields
            if partial:
                # Only use incoming items for duplicate check
                incoming_product_ids = [
                    item_data['product'].id if hasattr(item_data['product'], 'id') else int(item_data['product'])
                    for item_data in items_data if 'product' in item_data
                ]
                if len(incoming_product_ids) != len(set(incoming_product_ids)):
                    raise serializers.ValidationError("Duplicate products found in items. Each product should be unique.")
                existing_items = {item.product.id: item for item in instance.items.all()}
                for item_data in items_data:
                    product_id = item_data['product'].id if hasattr(item_data['product'], 'id') else int(item_data['product'])
                    if product_id in existing_items:
                        pr_item = existing_items[product_id]
                        for attr, value in item_data.items():
                            if attr != 'id' and attr != 'product':
                                setattr(pr_item, attr, value)
                        pr_item.save()
                    else:
                        PurchaseRequestItem.objects.create(purchase_request=instance, **item_data)
            else:
                existing_items = {item.id: item for item in instance.items.all()}
                for item_data in items_data:
                    item_id = item_data.get('id')
                    if item_id and item_id in existing_items:
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(existing_items[item_id], attr, value)
                        existing_items[item_id].save()
                    else:
                        PurchaseRequestItem.objects.create(purchase_request=instance, **item_data)
        return instance



class RequestForQuotationItemSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='request-for-quotation-item-detail')
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_hidden=False),
    )
    unit_of_measure = serializers.PrimaryKeyRelatedField(
        queryset=UnitOfMeasure.objects.filter(is_hidden=False),
        required=False,
        allow_null=True,
        allow_empty=True
    )
    request_for_quotation = serializers.PrimaryKeyRelatedField(
        read_only=True
    )
    # This field is a custom property on the model, not a serializer field.
    get_total_price = serializers.ReadOnlyField()
    product_details = ProductSerializer(read_only=True, source='product')

    class Meta:
        model = RequestForQuotationItem
        fields = ['id', 'url', 'request_for_quotation', 'product', 'product_details', 'description',
                  'qty', 'unit_of_measure', 'estimated_unit_price', 'get_total_price']

    def validate(self, data):
        if data.get('qty') is None or data['qty'] <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return data

    def create(self, validated_data):
        if not validated_data.get('description'):
            validated_data['description'] = validated_data['product'].product_description
        if not validated_data.get('unit_of_measure'):
            validated_data['unit_of_measure'] = validated_data['product'].unit_of_measure
        return super().create(validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            if attr != 'id':
                setattr(instance, attr, value)
        if not instance.description:
            instance.description = instance.product.product_description
        if not instance.unit_of_measure:
            instance.unit_of_measure = instance.product.unit_of_measure
        instance.save()
        return instance

class RequestForQuotationSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='request-for-quotation-detail')
    purchase_request = serializers.PrimaryKeyRelatedField(
        required=False,
        allow_null=True,
        allow_empty=True,
        queryset=PurchaseRequest.objects.filter(is_hidden=False)
    )
    currency = serializers.PrimaryKeyRelatedField(
        queryset=Currency.objects.filter(is_hidden=False),
    )
    vendor = serializers.PrimaryKeyRelatedField(
        queryset=Vendor.objects.filter(is_hidden=False),
    )
    rfq_total_price = serializers.ReadOnlyField()
    items = RequestForQuotationItemSerializer(many=True)
    currency_details = CurrencySerializer(source='currency', read_only=True)
    vendor_details = VendorSerializer(source='vendor', read_only=True)

    class Meta:
        model = RequestForQuotation
        fields = ['url', 'id', 'expiry_date', 'vendor', 'purchase_request', 'currency',
                  'status', 'rfq_total_price', 'items', 'is_hidden', 'is_expired', 'is_submitted',
                  'can_edit', 'vendor_details', 'currency_details']
        read_only_fields = ['date_created', 'date_updated', 'rfq_total_price']

    def validate_create(self, data):
        if data['purchase_request'] is None:
            raise serializers.ValidationError("Purchase request is required.")
        if data.get('purchase_request') and data['purchase_request'].status != "approved":
            raise serializers.ValidationError("Purchase request must be approved before creating a RFQ.")
        if data['vendor'] is None:
            raise serializers.ValidationError("Vendor is required.")
        if data['currency'] is None:
            raise serializers.ValidationError("Currency is required.")
        if data['expiry_date'] < data['purchase_request'].date_created:
            raise serializers.ValidationError("Expiry date cannot be earlier than the purchase request creation date.")
        if not data['items']:
            raise serializers.ValidationError("At least one item is required to create a RFQ.")
        items_data = data.get('items', [])
        incoming_product_ids = [
            item['product'].id if hasattr(item['product'], 'id') else int(item['product'])
            for item in items_data if 'product' in item
        ]
        if self.instance:
            existing_product_ids = [
                item.product.id for item in self.instance.items.all()
            ]
        else:
            existing_product_ids = []
        all_product_ids = incoming_product_ids + existing_product_ids
        if len(all_product_ids) != len(set(all_product_ids)):
            raise serializers.ValidationError("Duplicate products found in items. Each product should be unique.")

        # Prevent duplicate RFQ creation
        if RequestForQuotation.objects.filter(
            purchase_request=data['purchase_request'],
            expiry_date=data['expiry_date'],
            vendor=data['vendor'],
            status__in=['draft', 'pending'],  # Exclude approved and rejected RFQs
            currency=data['currency'],
            items__product__in=[item['product'] for item in data.get('items', [])],
            is_hidden=False
        ).exists():
            raise serializers.ValidationError("A RFQ with these details already exists.")
        return data

    def validate_update(self, data):
        if 'items' in data:
            items = data['items']
            if not items:
                raise serializers.ValidationError("At least one item is required for a partial update.")
            incoming_product_ids = [
                item['product'].id if hasattr(item['product'], 'id') else int(item['product'])
                for item in items if 'product' in item
            ]
            if self.instance:
                existing_product_ids = [
                    item.product.id for item in self.instance.items.all()
                ]
            else:
                existing_product_ids = []
            all_product_ids = incoming_product_ids + existing_product_ids
            if len(all_product_ids) != len(set(all_product_ids)):
                raise serializers.ValidationError("Duplicate products found in items. Each product should be unique.")
        required_fields = ['purchase_request', 'currency', 'vendor', 'expiry_date']
        if data.get('purchase_request') and data['purchase_request'].status != 'approved':
            raise serializers.ValidationError("The purchase request must be approved before creating a RFQ.")
        for field in required_fields:
            if field in data and data[field] is None:
                raise serializers.ValidationError(f"{field.replace('_', ' ').capitalize()} is required.")
        return data

    def validate(self, data):
        if self.instance is None:
            self.validate_create(data)
        else:
            self.validate_update(data)
        return data


    def create(self, validated_data):
        items_data = validated_data.pop('items')
        rfq = RequestForQuotation.objects.create(**validated_data)
        # use bulk_create for efficiency
        RequestForQuotationItem.objects.bulk_create(
            [RequestForQuotationItem(
                request_for_quotation=rfq,
                **item_data
            ) for item_data in items_data])
        return rfq

    def update(self, instance, validated_data):
        partial = self.context.get('partial', False)
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            # If partial, handle only provided fields
            if partial:
                # custom partial update logic here
                existing_items = {item.product.id: item for item in instance.items.all()}
                incoming_product_ids = set()
                for item_data in items_data:
                    product_id = item_data['product'].id if hasattr(item_data['product'], 'id') else int(item_data['product'])
                    incoming_product_ids.add(product_id)
                    if product_id in existing_items:
                        rfq_item = existing_items[product_id]
                        for attr, value in item_data.items():
                            if attr != 'id' and attr != 'product':
                                setattr(rfq_item, attr, value)
                        rfq_item.save()
                    else:
                        RequestForQuotationItem.objects.create(request_for_quotation=instance, **item_data)
                        # Do not delete items not present in the update
            else:
                # full update logic here
                existing_items = {item.id: item for item in instance.items.all()}
                for item_data in items_data:
                    item_id = item_data.get('id')
                    if item_id and item_id in existing_items:
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(existing_items[item_id], attr, value)
                        existing_items[item_id].save()
                    else:
                        RequestForQuotationItem.objects.create(request_for_quotation=instance, **item_data)
                        # Do not delete items not present in the update
        return instance


class PurchaseOrderItemSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='purchase-order-item-detail')
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_hidden=False),
    )
    purchase_order = serializers.PrimaryKeyRelatedField(
        read_only=True
    )
    unit_of_measure = serializers.PrimaryKeyRelatedField(
        queryset=UnitOfMeasure.objects.filter(is_hidden=False),
        required=False,
        allow_null=True,
        allow_empty=True
    )
    # This field is a custom property on the model, not a serializer field.
    get_total_price = serializers.ReadOnlyField()
    product_details = ProductSerializer(read_only=True, source='product')

    class Meta:
        model = PurchaseOrderItem
        fields = ['id', 'url', 'purchase_order', 'product', 'description', 'product_details',
                  'qty', 'unit_of_measure', 'estimated_unit_price', 'get_total_price']

    def validate(self, data):
        if data.get('qty') is None or data['qty'] <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return data

    def create(self, validated_data):
        if not validated_data.get('description'):
            validated_data['description'] = validated_data['product'].product_description
        if not validated_data.get('unit_of_measure'):
            validated_data['unit_of_measure'] = validated_data['product'].unit_of_measure
        return super().create(validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            if attr != 'id':
                setattr(instance, attr, value)
        if not instance.description:
            instance.description = instance.product.product_description
        if not instance.unit_of_measure:
            instance.unit_of_measure = instance.product.unit_of_measure
        instance.save()
        return instance


class PurchaseOrderSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='purchase-order-detail', lookup_field='id',
                                               lookup_url_kwarg='id')
    created_by = serializers.PrimaryKeyRelatedField(
        queryset=TenantUser.objects.filter(is_hidden=False),
        required=False
    )
    items = PurchaseOrderItemSerializer(many=True)
    # add a one-to-one serializer field
    related_rfq = serializers.PrimaryKeyRelatedField(
        required=False,
        allow_null=True,
        allow_empty=True,
        queryset=RequestForQuotation.objects.filter(is_hidden=False)
    )
    destination_location = serializers.PrimaryKeyRelatedField(
        queryset=Location.get_active_locations().filter(is_hidden=False),
    )
    vendor = serializers.PrimaryKeyRelatedField(
        queryset=Vendor.objects.filter(is_hidden=False),
    )
    currency = serializers.PrimaryKeyRelatedField(
        queryset=Currency.objects.filter(is_hidden=False),
    )
    created_by_details = TenantUserSerializer(source='created_by', read_only=True)
    # This field is a custom property on the model, not a serializer field.
    po_total_price = serializers.ReadOnlyField()
    currency_details = CurrencySerializer(source='currency', read_only=True)
    destination_location_details = LocationSerializer(source='destination_location', read_only=True)
    vendor_details = VendorSerializer(source='vendor', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = ['id', 'url', 'status', 'date_created', 'date_updated', 'related_rfq', 'created_by',
                  'vendor', 'currency', 'payment_terms', 'destination_location', 'created_by_details',
                  'purchase_policy', 'delivery_terms', 'items', 'po_total_price', 'vendor_details',
                  'is_hidden', 'is_submitted', 'can_edit', 'currency_details', 'destination_location_details',]

    def to_internal_value(self, data):
        data = data.copy()
        if 'created_by' not in data or not data.get('created_by'):
            user = self.context['request'].user
            try:
                tenant_user = TenantUser.objects.get(user_id=user.id, is_hidden=False)
                data['created_by'] = tenant_user.pk
            except TenantUser.DoesNotExist:
                raise serializers.ValidationError({'created_by': 'Logged in user is not a valid tenant member.'})
        return super().to_internal_value(data)

    def validate_create(self, data):
        required_fields = ['items', 'created_by', 'currency', 'vendor',  'related_rfq', 'created_by',
                           'destination_location']
        if data.get('related_rfq') and data['related_rfq'].status != "approved":
            raise serializers.ValidationError("RFQ must be approved before creating a Purchase Order.")
        for field in required_fields:
            if not data.get(field):
                raise serializers.ValidationError(
                    f"{field.replace('_', ' ').capitalize()} is required to create a purchase request."
                )
        if data.get('destination_location') is None and not MultiLocation.objects.filter(is_activated=False).exists():
            raise serializers.ValidationError("Destination location is required when multi-location is activated.")
        if PurchaseOrder.objects.filter(
            created_by=data.get('created_by'),
            related_rfq=data.get('related_rfq'),
            destination_location=data.get('destination_location'),
            vendor=data.get('vendor'),
            status__in=['draft', 'pending'],
            currency=data.get('currency'),
            items__product__in=[item['product'] for item in data.get('items', [])],
            is_hidden=False
        ).exists():
            raise serializers.ValidationError("A purchase order with these details already exists.")
        items_data = data.get('items', [])
        if not items_data:
            raise serializers.ValidationError("At least one item is required to create a purchase order.")
        incoming_product_ids = [
            item['product'].id if hasattr(item['product'], 'id') else int(item['product'])
            for item in items_data if 'product' in item
        ]
        if self.instance:
            existing_product_ids = [
                item.product.id for item in self.instance.items.all()
            ]
        else:
            existing_product_ids = []
        all_product_ids = incoming_product_ids + existing_product_ids
        if len(all_product_ids) != len(set(all_product_ids)):
            raise serializers.ValidationError("Duplicate products found in items. Each product should be unique.")
        return data

    def validate_update(self, data):
        if 'items' in data:
            items = data['items']
            if not items:
                raise serializers.ValidationError("At least one item is required for a partial update.")
            incoming_product_ids = [
                item['product'].id if hasattr(item['product'], 'id') else int(item['product'])
                for item in items if 'product' in item
            ]
            if self.instance:
                existing_product_ids = [
                    item.product.id for item in self.instance.items.all()
                ]
            else:
                existing_product_ids = []
            all_product_ids = incoming_product_ids + existing_product_ids
            if len(all_product_ids) != len(set(all_product_ids)):
                raise serializers.ValidationError("Duplicate products found in items. Each product should be unique.")
        required_fields = ['destination_location', 'created_by', 'currency', 'vendor', 'related_rfq']
        if data.get('related_rfq') and data['related_rfq'].status != "approved":
            raise serializers.ValidationError("RFQ must be approved before creating a Purchase Order.")
        for field in required_fields:
            if field in data and data[field] is None:
                raise serializers.ValidationError(f"{field.replace('_', ' ').capitalize()} is required.")
        if 'destination_location' in data and data['destination_location'] is None and not MultiLocation.objects.filter(is_activated=False).exists():
            raise serializers.ValidationError("Destination location is required when multi-location is activated.")

        return data

    def validate(self, data):
        if self.instance is None:
            self.validate_create(data)
        else:
            self.validate_update(data)
        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        if not items_data:
            raise serializers.ValidationError("At least one item is required to create a purchase order.")
        po = PurchaseOrder.objects.create(**validated_data)
        PurchaseOrderItem.objects.bulk_create(
            [PurchaseOrderItem(
                purchase_order=po,
                **item_data
            ) for item_data in items_data]
        )
        return po

    def update(self, instance, validated_data):
        partial = self.context.get('partial', False)
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            # If partial, handle only provided fields
            if partial:
                # custom partial update logic here
                existing_items = {item.product.id: item for item in instance.items.all()}
                incoming_product_ids = set()
                for item_data in items_data:
                    product_id = item_data['product'].id if hasattr(item_data['product'], 'id') else int(item_data['product'])
                    incoming_product_ids.add(product_id)
                    if product_id in existing_items:
                        po_item = existing_items[product_id]
                        for attr, value in item_data.items():
                            if attr != 'id' and attr != 'product':
                                setattr(po_item, attr, value)
                        po_item.save()
                    else:
                        PurchaseOrderItem.objects.create(purchase_order=instance, **item_data)
            else:
                existing_items = {item.id: item for item in instance.items.all()}
                for item_data in items_data:
                    item_id = item_data.get('id')
                    if item_id and item_id in existing_items:
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(existing_items[item_id], attr, value)
                        existing_items[item_id].save()
                    else:
                        PurchaseOrderItem.objects.create(purchase_order=instance, **item_data)
        return instance
