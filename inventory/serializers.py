from rest_framework import serializers
from django.db import IntegrityError, transaction

from purchase.models import Product, PurchaseOrder
from purchase.serializers import ProductSerializer, VendorSerializer, PurchaseOrderSerializer

from users.models import TenantUser


from .models import (DeliveryOrder, DeliveryOrderItem, DeliveryOrderReturn, DeliveryOrderReturnItem, Location, MultiLocation, ReturnIncomingProduct, ReturnIncomingProductItem, StockAdjustment, StockAdjustmentItem,
                     Scrap, ScrapItem, IncomingProductItem, IncomingProduct, INCOMING_PRODUCT_RECEIPT_TYPES)


class LocationSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='location-detail', lookup_field='id')
    location_manager = serializers.HyperlinkedRelatedField(queryset=TenantUser.objects.filter(is_hidden=False),
                                                           view_name='tenant-user-detail', allow_null=True)
    store_keeper = serializers.HyperlinkedRelatedField(queryset=TenantUser.objects.filter(is_hidden=False),
                                                       view_name='tenant-user-detail', allow_null=True)
    id = serializers.CharField(required=False)  # Make the id field read-only

    class Meta:
        model = Location
        fields = ['url', 'id', 'location_code', 'location_name', 'location_type', 'address', 'location_manager',
                  'store_keeper', 'contact_information', 'is_hidden']
        read_only_fields = ['date_created', 'date_updated', ]
        extra_kwargs = {
            'url': {'view_name': 'location-detail', 'lookup_field': 'id'}  # Ensure this matches the `lookup_field`
        }


class MultiLocationSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='multi-location-detail')

    class Meta:
        model = MultiLocation
        fields = ['url', 'is_activated']


class StockAdjustmentItemSerializer(serializers.ModelSerializer):
    # url = serializers.HyperlinkedIdentityField(view_name='stock-adjustment-item-detail')
    stock_adjustment = serializers.HyperlinkedRelatedField(
        view_name='stock-adjustment-detail',
        read_only=True,
        lookup_field='id',  # ✅ use 'id' as lookup field
        lookup_url_kwarg='id',
    )
    product = serializers.HyperlinkedRelatedField(queryset=Product.objects.filter(is_hidden=False),
                                                  view_name='product-detail')
    id = serializers.CharField(required=False, read_only=True)  # Make the id field read-only

    class Meta:
        model = StockAdjustmentItem
        fields = ['id', 'product', 'unit_of_measure', 'current_quantity', 'adjusted_quantity',
                  'stock_adjustment']


class StockAdjustmentSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='stock-adjustment-detail',
                                               lookup_field='id',
                                               lookup_url_kwarg='id')
    warehouse_location = serializers.HyperlinkedRelatedField(queryset=Location.objects.filter(is_hidden=False),
                                                             view_name='location-detail',
                                                             lookup_url_kwarg='id',
                                                             lookup_field='id')

    stock_adjustment_items = StockAdjustmentItemSerializer(many=True)
    id = serializers.CharField(required=False, read_only=True)  # Make the id field read-only

    class Meta:
        model = StockAdjustment
        fields = ['url', 'id', 'adjustment_type', 'warehouse_location', 'notes', 'status', 'is_hidden',
                  'stock_adjustment_items', 'is_done', 'can_edit']
        read_only_fields = ['date_created', 'date_updated', 'adjustment_type']
        extra_kwargs = {
            'url': {'view_name': 'stock-adjustment-detail', 'lookup_field': 'id'}
            # Ensure this matches the `lookup_field`
        }

    def create(self, validated_data):
        """
        Create a new Stock Adjustment with its associated items.
        """
        items_data = validated_data.pop('stock_adjustment_items')
        if not items_data:
            raise serializers.ValidationError("At least one item is required to create a Stock Adjustment.")
        stock_adjustment = StockAdjustment.objects.create(**validated_data)
        for item_data in items_data:
            StockAdjustmentItem.objects.create(stock_adjustment=stock_adjustment, **item_data)
        return stock_adjustment

    def update(self, instance, validated_data):
        """
        Update an existing instance with validated data.
        """
        items_data = validated_data.pop('stock_adjustment_items', None)
        if items_data:
            # Clear existing items and add new ones
            instance.stock_adjustment_items.all().delete()
            for item_data in items_data:
                StockAdjustmentItem.objects.create(stock_adjustment=instance, **item_data)

        # Update the instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class ScrapItemSerializer(serializers.HyperlinkedModelSerializer):
    # url = serializers.HyperlinkedIdentityField(view_name='scrap-item-detail')
    scrap = serializers.HyperlinkedRelatedField(
        view_name='scrap-detail',
        read_only=True,
        lookup_field='id',  # ✅ use 'id' as lookup field
        lookup_url_kwarg='id',
    )
    product = serializers.HyperlinkedRelatedField(queryset=Product.objects.filter(is_hidden=False),
                                                  view_name='product-detail')
    id = serializers.CharField(required=False, read_only=True)  # Make the id field read-only

    class Meta:
        model = ScrapItem
        fields = ['id', 'scrap', 'product', 'scrap_quantity', 'adjusted_quantity']


class ScrapSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='scrap-detail', lookup_field='id')
    warehouse_location = serializers.HyperlinkedRelatedField(
        queryset=Location.objects.filter(is_hidden=False),
        view_name='location-detail',
        lookup_url_kwarg='id',
        lookup_field='id'
    )

    scrap_items = ScrapItemSerializer(many=True)
    id = serializers.CharField(required=False, read_only=True)  # Make the id field read-only


    class Meta:
        model = Scrap
        fields = ['url', 'id', 'adjustment_type', 'warehouse_location', 'notes', 'status',
                  'is_hidden', 'is_done', 'can_edit', 'scrap_items']
        read_only_fields = ['date_created', 'date_updated']
        extra_kwargs = {
            'url': {'view_name': 'scrap-detail', 'lookup_field': 'id'}
            # Ensure this matches the `lookup_field`
        }

    def create(self, validated_data):
        """
        Create a new Scrap with its associated items.
        """
        items_data = validated_data.pop('scrap_items')
        if not items_data:
            raise serializers.ValidationError("At least one item is required to create a Scrap.")
        scrap = Scrap.objects.create(**validated_data)
        for item_data in items_data:
            ScrapItem.objects.create(scrap=scrap, **item_data)
        return scrap

    def update(self, instance, validated_data):
        """
        Update an existing instance with validated data.
        """
        items_data = validated_data.pop('scrap_items', None)
        if items_data:
            # Clear existing items and add new ones
            instance.scrap_items.all().delete()
            for item_data in items_data:
                ScrapItem.objects.create(scrap=instance, **item_data)

        # Update the instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class IPItemSerializer(serializers.ModelSerializer):
    id = serializers.CharField(required=False, read_only=True)
    incoming_product = serializers.ReadOnlyField(source="incoming_product.incoming_product_id")

    class Meta:
        model = IncomingProductItem
        fields = ['id', 'incoming_product', 'product',
                  'expected_quantity', 'quantity_received']


class IncomingProductSerializer(serializers.ModelSerializer):
    incoming_product_items = IPItemSerializer(many=True)
    related_po = serializers.PrimaryKeyRelatedField(
        many=False,
        queryset=PurchaseOrder.objects.filter(is_hidden=False, status='completed'),
        allow_null=True
    )
    receipt_type = serializers.ChoiceField(choices=INCOMING_PRODUCT_RECEIPT_TYPES)
    user_choice = serializers.DictField(
        write_only=True,
        required=False,
        child=serializers.BooleanField(),
        default={'backorder': False, 'overpay': False},
        help_text="Valid keys are: 'backorder', 'overpay'."
    )
    backorder_of = serializers.ReadOnlyField()


    incoming_product_id = serializers.CharField(required=False, read_only=True)  # Make the id field read-only

    class Meta:
        model = IncomingProduct
        fields = ['incoming_product_id', 'receipt_type', 'related_po', 'backorder_of', 'user_choice',
                  'supplier', 'source_location', 'incoming_product_items', 'destination_location', 'status',
                  'is_validated', 'can_edit', 'is_hidden']
        read_only_fields = ['date_created', 'date_updated']

    def validate(self, data):
        # validation to ensure that the related purchase order is not already linked to another incoming product.
        related_po = data.get('related_po', None)
        if related_po and IncomingProduct.objects.filter(related_po=related_po).exists():
            raise serializers.ValidationError("This purchase order is already linked to another incoming product.")

        # Ensure that the items data is present and valid
        items_data = data.get('incoming_product_items', [])
        if not items_data:
            raise serializers.ValidationError("At least one item is required.")
        for item in items_data:
            product = item.get('product')
            expected_quantity = item.get('expected_quantity', None)
            quantity_received = item.get('quantity_received', 0)
            if not product:
                raise serializers.ValidationError("Invalid Product")
            if related_po:
                # Set expected_quantity from the corresponding PO item
                po_item = related_po.items.filter(product_id=product.id).first()
                if not po_item:
                    raise serializers.ValidationError("Product not found in related purchase order items.")
                else:
                    if expected_quantity is None:
                        raise serializers.ValidationError("Expected quantity is required if there is no related "
                                                          "purchase order.")
            if quantity_received < 0 or expected_quantity < 0:
                raise serializers.ValidationError("Quantities cannot be negative.")
        # Ensure that the user_choice is a dictionary if provided
        user_choice = data.get('user_choice', {})
        if not isinstance(user_choice, dict):
            raise serializers.ValidationError("User choice must be a dictionary.")
        if user_choice:
            # Ensure that the user_choice contains valid keys
            valid_keys = ['backorder', 'overpay']
            for key in user_choice.keys():
                if key not in valid_keys:
                    raise serializers.ValidationError(f"Invalid user choice key: {key}. Valid keys are: {', '.join(valid_keys)}")

        # Ensure that the receipt type is one of the allowed types
        receipt_type = data.get('receipt_type')
        # INCOMING_PRODUCT_RECEIPT_TYPES may be a list of tuples, so extract the valid values
        valid_receipt_types = [choice[0] if isinstance(choice, tuple) else choice for choice in INCOMING_PRODUCT_RECEIPT_TYPES]
        if receipt_type not in valid_receipt_types:
            raise serializers.ValidationError(
                "Invalid receipt type. Must be one of: " + ", ".join(str(v) for v in valid_receipt_types)
            )

        # Ensure that the supplier, source location, and destination location are provided
        if not data.get('supplier'):
            raise serializers.ValidationError("Supplier is required.")
        if not data.get('source_location'):
            raise serializers.ValidationError("Source location is required.")
        if not data.get('destination_location'):
            raise serializers.ValidationError("Destination location is required.")

        # Ensure when validated, all required fields are present
        if data.get('is_validated') and not data.get('destination_location'):
            raise serializers.ValidationError("Destination location is required when the incoming product is validated.")
        if data.get('is_validated') and not data.get('incoming_product_items'):
            raise serializers.ValidationError("At least one incoming product item is required when the incoming"
                                              "product is validated.")
        if data.get('is_validated') and not data.get('source_location'):
            raise serializers.ValidationError("Source location is required when the incoming product is validated.")
        if data.get('is_validated') and not data.get('supplier'):
            raise serializers.ValidationError("Supplier is required when the incoming product is validated.")
        if data.get('is_validated') and not data.get('receipt_type'):
            raise serializers.ValidationError("Receipt type is required when the incoming product is validated.")
        if data.get('is_validated') and not data.get('related_po'):
            raise serializers.ValidationError("Related purchase order is required when the incoming product is "
                                              "validated.")
        if data.get('is_validated') and data.get('related_po') and not PurchaseOrder.objects.filter(id=data['related_po'].id, is_hidden=False).exists():
            raise serializers.ValidationError("Related purchase order does not exist or is hidden.")
        if data.get('is_validated') and data.get('related_po') and not data.get('incoming_product_items'):
            raise serializers.ValidationError("At least one incoming product item is required when the incoming "
                                              "product is validated with a related purchase order.")

        return data

    def create(self, validated_data):
        """
        Create a new Incoming Product with its associated items.
        """
        items_data = validated_data.pop('incoming_product_items')
        user_choice = validated_data.pop('user_choice', {})
        related_po = validated_data.get('related_po', None)
        incoming_product = IncomingProduct.objects.create(**validated_data)
        backorder = incoming_product.process_receipt(items_data, user_choice)

        for item_data in items_data:
            product = item_data.get('product')
            expected_quantity = item_data.get('expected_quantity', None)
            quantity_received = item_data.get('quantity_received', 0)
            # Set expected_quantity from the corresponding PO item
            if related_po:
                po_item = related_po.items.filter(product_id=product.id).first()
                if po_item:
                    item_data['expected_quantity'] = po_item.qty
            else:
                item_data['expected_quantity'] = expected_quantity
            ip_item = IncomingProductItem.objects.create(incoming_product=incoming_product, **item_data)
            if not ip_item:
                raise serializers.ValidationError("Failed to create Incoming Product Item.")
            # Update product quantity if validated
            if incoming_product.is_validated:
                product.available_product_quantity += item_data['expected_quantity']
                product.save()
            if backorder:
                return {"incoming_product": incoming_product, "backorder": backorder}
        # If no backorder, just return the incoming product
        return incoming_product

    def update(self, instance, validated_data):
        """
        Update an existing instance with validated data.
        """
        items_data = validated_data.pop('incoming_product_items', None)
        user_choice = validated_data.pop('user_choice', {})
        related_po = validated_data.get('related_po', getattr(instance, 'related_po', None))
        if items_data:
            # Clear existing items and add new ones
            instance.incoming_product_items.all().delete()
            for item_data in items_data:
                product = item_data.get('product')
                expected_quantity = item_data.get('expected_quantity', None)
                quantity_received = item_data.get('quantity_received', 0)
                # Set expected_quantity from PO if related_po exists
                if related_po:
                    po_item = related_po.items.filter(product_id=product.id).first()
                    if po_item:
                        item_data['expected_quantity'] = po_item.qty
                    else:
                        raise serializers.ValidationError("Product not found in related purchase order items.")
                else:
                    item_data['expected_quantity'] = expected_quantity
                ip_item = IncomingProductItem.objects.create(incoming_product=instance, **item_data)
                if not ip_item:
                    raise serializers.ValidationError("Failed to create Incoming Product Item.")
                # Update product quantity if validated
                if instance.is_validated:
                    product.available_product_quantity += item_data['expected_quantity']
                    product.save()

        # Update the instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance



# START THE DELIVERY ORDERS
class DeliveryOrderItemSerializer(serializers.ModelSerializer):
    delivery_order = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = DeliveryOrderItem
        exclude = ('is_hidden',)


class DeliveryOrderSerializer(serializers.ModelSerializer):
    delivery_order_items = DeliveryOrderItemSerializer(many=True)
    order_unique_id = serializers.CharField(read_only=True)
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = DeliveryOrder
        fields = ['id', 'order_unique_id', 'customer_name', 'source_location', 
                  'delivery_address', 'delivery_date', 'shipping_policy', 
                  'return_policy', 'assigned_to', 'delivery_order_items', 'status', 'date_created']

    @transaction.atomic
    def create(self, validated_data):
        products_data = validated_data.pop('delivery_order_items')
        try:
            delivery_order = DeliveryOrder.objects.create(**validated_data)
            delivery_order_items = []
            for product_data in products_data:
                one_item = DeliveryOrderItem(delivery_order=delivery_order, **product_data)
                delivery_order_items.append(one_item)
            DeliveryOrderItem.objects.bulk_create(delivery_order_items)
            return delivery_order
        except IntegrityError as e:
            raise serializers.ValidationError({"detail": "Error creating delivery order: " + str(e)})

    @transaction.atomic
    def update(self, instance, validated_data):
        products_data = validated_data.pop('delivery_order_items')
        # Update parent fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        existing_products = {prod.id: prod for prod in instance.products.all()}
        sent_product_ids = []
        try:
            for prod_data in products_data:
                prod_id = prod_data.get('id', None)
                if prod_id and prod_id in existing_products:
                    # Update existing product
                    product = existing_products[prod_id]
                    for attr, value in prod_data.items():
                        setattr(product, attr, value)
                    product.save()
                    sent_product_ids.append(prod_id)
                else:
                    # Create new product related to this delivery order
                    DeliveryOrderItem.objects.create(delivery_order=instance, **prod_data)

            # Delete products not in the update list
            for prod_id, product in existing_products.items():
                if prod_id not in sent_product_ids:
                    product.delete()
            return instance
        except IntegrityError as e:
            raise serializers.ValidationError({"detail": "Error updating delivery order: " + str(e)})
        except Exception as e:
            raise serializers.ValidationError({"detail": "An unexpected error occurred: " + str(e)})

# END THE DELIVERY O


# START THE RETURN RECORD
class DeliveryOrderReturnItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = DeliveryOrderReturnItem
        fields = ['returned_product_item', 'initial_quantity', 'returned_quantity']


class DeliveryOrderReturnSerializer(serializers.ModelSerializer):
    unique_record_id = serializers.CharField(read_only=True)
    delivery_order_return_items = DeliveryOrderReturnItemSerializer(many=True)

    class Meta:
        model = DeliveryOrderReturn
        fields = [
            'unique_record_id',
            'source_document',
            'date_of_return',
            'source_location',
            'return_warehouse_location',
            'reason_for_return',
            'delivery_order_return_items',
        ]
        
    @transaction.atomic
    def create(self, validated_data):
        return_products_data = validated_data.pop('delivery_order_return_items')
        try:
            delivery_order_return = DeliveryOrderReturn.objects.create(**validated_data)
            returned_product_list = []
            for product_data in return_products_data:
                one_product = DeliveryOrderReturnItem(delivery_order_return=delivery_order_return, **product_data)
                returned_product_list.append(one_product)
            DeliveryOrderReturnItem.objects.bulk_create(returned_product_list)
            return delivery_order_return
        except IntegrityError as e:
            raise serializers.ValidationError(f"Database error occurred: {str(e)}")
        except Exception as e:
            raise serializers.ValidationError(f"An error occurred: {str(e)}")

# END THE RETURN REDORD


# START RETURN INCOMING PRODUCT
class ReturnIncomingProductItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), write_only=True)
    product_details = ProductSerializer(source="product", read_only=True)
    class Meta:
        model = ReturnIncomingProductItem
        fields = ["id", "product", "quantity_received", "quantity_to_be_returned", "product_details"]


class ReturnIncomingProductSerializer(serializers.ModelSerializer):
    unique_id = serializers.CharField(read_only=True)
    return_incoming_product_items = ReturnIncomingProductItemSerializer(many=True)
    is_approved = serializers.BooleanField(read_only=True)
    source_document = serializers.PrimaryKeyRelatedField(queryset=IncomingProduct.objects.all(), write_only=True)
    source_document_details = IncomingProductSerializer(source="source_document", read_only=True)
    class Meta:
        model = ReturnIncomingProduct
        fields = ["unique_id", "return_incoming_product_items", "source_document_details",
                  "source_document", "reason_for_return", "returned_date", "is_approved"]

    @transaction.atomic
    def create(self, validated_data):
        return_products_data = validated_data.pop('return_incoming_product_items')
        try:
            
            return_incoming_product = ReturnIncomingProduct.objects.create(**validated_data)
            returned_product_list = []
            for product_data in return_products_data:
                one_product = ReturnIncomingProductItem(return_incoming_product=return_incoming_product, **product_data)
                returned_product_list.append(one_product)                
            ReturnIncomingProductItem.objects.bulk_create(returned_product_list)
            return return_incoming_product
        except IntegrityError as e:
            raise serializers.ValidationError(f"Database error occurred: {str(e)}")
        except Exception as e:
            raise serializers.ValidationError(f"An error occurred: {str(e)}")


# END RETURN INCOMING PRODUCT