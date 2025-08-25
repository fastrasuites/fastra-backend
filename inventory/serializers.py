from rest_framework import serializers
from django.db import IntegrityError, transaction
from datetime import datetime
from django.core.exceptions import ValidationError as DjangoValidationError

from inventory.signals import create_delivery_order_returns_stock_move
from purchase.models import Product, PurchaseOrder
from purchase.serializers import ProductSerializer, VendorSerializer, PurchaseOrderSerializer
from shared.serializers import GenericModelSerializer

from users.models import TenantUser
from users.serializers import TenantUserSerializer


from .models import (DeliveryOrder, DeliveryOrderItem, DeliveryOrderReturn, DeliveryOrderReturnItem, Location,
                     MultiLocation, ReturnIncomingProduct, ReturnIncomingProductItem, StockAdjustment,
                     StockAdjustmentItem, BackOrder, BackOrderItem,
                     Scrap, ScrapItem, IncomingProductItem, IncomingProduct, INCOMING_PRODUCT_RECEIPT_TYPES, StockMove,
                     LocationStock, InternalTransfer, InternalTransferItem)


class LocationSerializer(serializers.HyperlinkedModelSerializer):
    location_manager = serializers.PrimaryKeyRelatedField(
                        queryset=TenantUser.objects.filter(is_hidden=False), allow_null=True)
    store_keeper = serializers.PrimaryKeyRelatedField(
                        queryset=TenantUser.objects.filter(is_hidden=False), allow_null=True)
    id = serializers.CharField(required=False)  # Make the id field read-only
    location_manager_details = TenantUserSerializer(source='location_manager', read_only=True)
    store_keeper_details = TenantUserSerializer(source='store_keeper', read_only=True)

    class Meta:
        model = Location
        fields = ['id', 'location_code', 'location_name', 'location_type', 'address', 'location_manager',
                  'location_manager_details', 'store_keeper', 'store_keeper_details', 'contact_information',
                  'is_hidden']
        read_only_fields = ['date_created', 'date_updated', ]
        

    def create(self, validated_data):
        if MultiLocation.objects.exists():
            multilocation = MultiLocation.objects.first()  # Adjust as needed
            if (not multilocation.is_activated
                    and Location.get_active_locations().filter(is_hidden=False).count() >= 1):
                raise serializers.ValidationError("max numbers of locations reached")
        else:
            MultiLocation.objects.create(is_activated=False)
        return super().create(validated_data)


class MultiLocationSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='multi-location-detail')

    class Meta:
        model = MultiLocation
        fields = ['url', 'is_activated']

    def validate(self, data):
        # Get the current instance if updating
        instance = getattr(self, 'instance', None)
        is_activated = data.get('is_activated', getattr(instance, 'is_activated', None))

        # You may need to adjust this depending on your model's relationship
        locations_count = Location.get_active_locations().filter(is_hidden=False).count()  # Or filter by tenant/org if needed

        if not is_activated and locations_count > 1:
            raise serializers.ValidationError("reduce number of locations to one before deactivating")

        return data


class StockAdjustmentItemSerializer(serializers.ModelSerializer):
    # url = serializers.HyperlinkedIdentityField(view_name='stock-adjustment-item-detail')
    stock_adjustment = serializers.HyperlinkedRelatedField(
        view_name='stock-adjustment-detail',
        read_only=True,
        lookup_field='id',  # ✅ use 'id' as lookup field
        lookup_url_kwarg='id',
    )
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_hidden=False),
    )
    current_quantity = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True,
        help_text="Current quantity in the warehouse location before adjustment."
    )
    product_details = ProductSerializer(source='product', read_only=True)
    id = serializers.CharField(required=False)

    class Meta:
        model = StockAdjustmentItem
        fields = ['id', 'product', 'unit_of_measure', 'adjusted_quantity', 'stock_adjustment',
                  'effective_quantity', 'current_quantity', 'product_details']


class StockAdjustmentSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='stock-adjustment-detail',
                                               lookup_field='id',
                                               lookup_url_kwarg='id')
    warehouse_location = serializers.PrimaryKeyRelatedField(
        queryset=Location.get_active_locations().filter(is_hidden=False),
        required=False
    )
    warehouse_location_details = LocationSerializer(source='warehouse_location', read_only=True)
    stock_adjustment_items = StockAdjustmentItemSerializer(many=True)
    id = serializers.CharField(required=False)  # Make the id field read-only

    class Meta:
        model = StockAdjustment
        fields = ['url', 'id', 'adjustment_type', 'warehouse_location', 'warehouse_location_details', 'notes', 'status', 'is_hidden',
                  'stock_adjustment_items', 'is_done', 'can_edit']
        read_only_fields = ['date_created', 'date_updated', 'adjustment_type']
        extra_kwargs = {
            'url': {'view_name': 'stock-adjustment-detail', 'lookup_field': 'id'}
            # Ensure this matches the `lookup_field`
        }

    def validate(self, attrs):
        """
        Validate the Stock Adjustment data.
        """
        if attrs.get('adjustment_type'):
            raise serializers.ValidationError("Field Adjustment type cannot be updated")
        if not self.instance:
            items_data = attrs.get('stock_adjustment_items', [])
            if not items_data:
                raise serializers.ValidationError("At least one item is required to create a Stock Adjustment.")
            for item in items_data:
                product = item.get('product')
                adjusted_quantity = item.get('adjusted_quantity', 0)
                if adjusted_quantity < 0:
                    raise serializers.ValidationError("Adjusted quantity cannot be negative.")
                if not Product.objects.filter(id=product.id, is_hidden=False).exists():
                    raise serializers.ValidationError("Invalid Product")
        return attrs

    def create(self, validated_data):
        """
        Create a new Stock Adjustment with its associated items.
        """
        if not validated_data.get('warehouse_location') and MultiLocation.objects.filter(is_activated=False).exists():
            validated_data['warehouse_location'] = Location.get_active_locations().first()
        items_data = validated_data.pop('stock_adjustment_items')
        stock_adjustment = StockAdjustment.objects.create(**validated_data)
        warehouse_location = stock_adjustment.warehouse_location

        for item_data in items_data:
            product = item_data['product']
            adjusted_quantity = item_data['adjusted_quantity']
            StockAdjustmentItem.objects.create(stock_adjustment=stock_adjustment, **item_data)
            # Update per-location stock
            # Update product quantity if done
            if stock_adjustment.status == "done":
                location_stock, created = LocationStock.objects.get_or_create(
                    location=warehouse_location, product=product,
                    defaults={'quantity': 0}
                )
                if location_stock:
                    location_stock.quantity = adjusted_quantity
                    location_stock.save()
                else:
                    raise serializers.ValidationError(
                        "Product does not exist in the specified warehouse location."
                    )
        return stock_adjustment

    def update(self, instance, validated_data):
        """
        Update an existing instance with validated data.
        """
        partial = self.context.get('partial', False)
        items_data = validated_data.pop('stock_adjustment_items', None)
        status = validated_data.get('status', None)
        was_validated = instance.status == 'done'
        is_now_validated = status == 'done'
        if status and status != instance.status:
            if status not in ['draft', 'done']:
                raise serializers.ValidationError("Invalid status value. Must be one of: draft, done.")
        if was_validated:
            raise serializers.ValidationError(
                "Stock Adjustment cannot be updated once the status is set to 'done'."
            )
        warehouse_location = validated_data.get('warehouse_location', instance.warehouse_location)

        # Update instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data:
            existing_items = {item.id: item for item in instance.stock_adjustment_items.all()}
            incoming_item_ids = set(item_data.get('id') for item_data in items_data if item_data.get('id'))

            if partial:
                # Only update or add provided items, do not delete others
                for item_data in items_data:
                    item_id = item_data.get('id')
                    if item_id and item_id in existing_items:
                        stock_adjustment_item = existing_items[item_id]
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(stock_adjustment_item, attr, value)
                        stock_adjustment_item.save()
                    else:
                        StockAdjustmentItem.objects.create(stock_adjustment=instance, **item_data)
            else:
                # Full update: delete items not present, update/add others
                for item_id in set(existing_items.keys()) - incoming_item_ids:
                    existing_items[item_id].delete()
                for item_data in items_data:
                    item_id = item_data.get('id')
                    if item_id and item_id in existing_items:
                        stock_adjustment_item = existing_items[item_id]
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(stock_adjustment_item, attr, value)
                        stock_adjustment_item.save()
                    else:
                        StockAdjustmentItem.objects.create(stock_adjustment=instance, **item_data)


        # Update per-location stock
        # Only update stock if the status is being changed to done in this update

        if not was_validated and is_now_validated:
            for item in instance.stock_adjustment_items.all():
                product = item.product
                adjusted_quantity = item.adjusted_quantity
                location_stock, created = LocationStock.objects.get_or_create(
                    location=warehouse_location, product=product,
                    defaults={'quantity': 0}
                )
                if location_stock:
                    location_stock.quantity = adjusted_quantity
                    location_stock.save()
                else:
                    raise serializers.ValidationError(
                        "Product does not exist in the specified warehouse location."
                    )
        return instance


class ScrapItemSerializer(serializers.HyperlinkedModelSerializer):
    # url = serializers.HyperlinkedIdentityField(view_name='scrap-item-detail')
    scrap = serializers.HyperlinkedRelatedField(
        view_name='scrap-detail',
        read_only=True,
        lookup_field='id',  # ✅ use 'id' as lookup field
        lookup_url_kwarg='id',
    )
    # product = serializers.HyperlinkedRelatedField(queryset=Product.objects.filter(is_hidden=False),
    #                                               view_name='product-detail')
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_hidden=False)
    )
    id = serializers.CharField(required=False)  # Make the id field read-only
    scrap_quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    adjusted_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    product_details = ProductSerializer(source='product', read_only=True)

    class Meta:
        model = ScrapItem
        fields = ['id', 'scrap', 'product', 'scrap_quantity', 'adjusted_quantity', 'product_details']


class ScrapSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='scrap-detail', lookup_field='id')
    warehouse_location = serializers.PrimaryKeyRelatedField(
        queryset=Location.get_active_locations().filter(is_hidden=False),
        required=False
    )
    warehouse_location_details = LocationSerializer(source='warehouse_location', read_only=True)
    scrap_items = ScrapItemSerializer(many=True)
    id = serializers.CharField(required=False)  # Make the id field read-only


    class Meta:
        model = Scrap
        fields = ['url', 'id', 'adjustment_type', 'warehouse_location', 'warehouse_location_details', 'notes', 'status',
                  'is_hidden', 'is_done', 'can_edit', 'scrap_items']
        read_only_fields = ['date_created', 'date_updated']
        extra_kwargs = {
            'url': {'view_name': 'scrap-detail', 'lookup_field': 'id'}
            # Ensure this matches the `lookup_field`
        }

    def validate(self, data):
        """
        Validate the Scrap data.
        """
        items_data = data.get('scrap_items', [])
        if not self.instance and not items_data:
            raise serializers.ValidationError("At least one item is required to create a Scrap.")
        if items_data:
            for item in items_data:
                product = item.get('product')
                scrap_quantity = item.get('scrap_quantity', 0)
                if scrap_quantity <= 0:
                    raise serializers.ValidationError("Scrap quantity cannot be zero or negative.")
                if not Product.objects.filter(id=product.id, is_hidden=False).exists():
                    raise serializers.ValidationError("Invalid Product")
        return data

    @transaction.atomic
    def create(self, validated_data):
        """
        Create a new Scrap with its associated items.
        """
        if not validated_data.get('warehouse_location') and MultiLocation.objects.filter(is_activated=False).exists():
            validated_data['warehouse_location'] = Location.get_active_locations().first()
        items_data = validated_data.pop('scrap_items')
        scrap = Scrap.objects.create(**validated_data)
        warehouse_location = scrap.warehouse_location
        for item_data in items_data:
            product = item_data['product']
            scrap_quantity = item_data['scrap_quantity']
            item_data.pop('product')
            try:
                ScrapItem.objects.create(scrap=scrap, product=product, **item_data)
            except DjangoValidationError as e:
                raise serializers.ValidationError({
                    'detail': [f"Error for product {product.id}: {e.message}"]
                })
            # Update per-location stock
            # Update product quantity if done
            if scrap.status == "done":
                location_stock = LocationStock.objects.filter(
                    location=warehouse_location, product=product,
                ).first()
                if location_stock:
                    location_stock.quantity -= scrap_quantity
                    location_stock.save()
                else:
                    raise serializers.ValidationError(
                        "Product does not exist in the specified warehouse location."
                    )
        return scrap

    def update(self, instance, validated_data):
        partial = self.context.get('partial', False)
        items_data = validated_data.pop('scrap_items', None)
        status = validated_data.get('status', None)
        was_validated = instance.status == 'done'
        is_now_validated = status == 'done'
        warehouse_location = validated_data.get('warehouse_location', instance.warehouse_location)

        if was_validated:
            raise serializers.ValidationError(
                "Scrap cannot be updated once the status is set to 'done'."
            )

        # Update instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            existing_items = {item.id: item for item in instance.scrap_items.all()}
            incoming_item_ids = set(item_data.get('id') for item_data in items_data if item_data.get('id'))

            if partial:
                # Only update or add provided items, do not delete others
                for item_data in items_data:
                    item_id = item_data.get('id')
                    if item_id and item_id in existing_items:
                        scrap_item = existing_items[item_id]
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(scrap_item, attr, value)
                        scrap_item.save()
                    else:
                        ScrapItem.objects.create(scrap=instance, **item_data)
            else:
                # Full update: delete items not present, update/add others
                for item_id in set(existing_items.keys()) - incoming_item_ids:
                    existing_items[item_id].delete()
                for item_data in items_data:
                    item_id = item_data.get('id')
                    if item_id and item_id in existing_items:
                        scrap_item = existing_items[item_id]
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(scrap_item, attr, value)
                        scrap_item.save()
                    else:
                        ScrapItem.objects.create(scrap=instance, **item_data)

        # Update location stock if status changed to "done"
        if not was_validated and is_now_validated:
            for item in instance.scrap_items.all():
                product = item.product
                scrap_quantity = item.scrap_quantity
                location_stock = LocationStock.objects.filter(
                    location=warehouse_location, product=product
                ).first()
                if not location_stock:
                    raise serializers.ValidationError("Location stock not found for the product.")
                if location_stock.quantity < scrap_quantity:
                    raise serializers.ValidationError("Insufficient stock to scrap this quantity.")
                location_stock.quantity -= scrap_quantity
                location_stock.save()

        return instance


class IPItemSerializer(serializers.ModelSerializer):
    id = serializers.CharField(required=False)
    incoming_product = serializers.ReadOnlyField(source="incoming_product.incoming_product_id")
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_hidden=False),
    )
    product_details = ProductSerializer(source='product', read_only=True)

    class Meta:
        model = IncomingProductItem
        fields = ['id', 'incoming_product', 'product', 'product_details',
                  'expected_quantity', 'quantity_received']
        extra_kwargs = {
            'id': {'required': False, 'allow_null': True},
        }


class IncomingProductSerializer(serializers.ModelSerializer):
    incoming_product_items = IPItemSerializer(many=True)
    related_po = serializers.PrimaryKeyRelatedField(
        many=False,
        queryset=PurchaseOrder.objects.filter(is_hidden=False, status='completed'),
        allow_null=True,
        allow_empty=True,
        required=False,
    )
    receipt_type = serializers.ChoiceField(choices=INCOMING_PRODUCT_RECEIPT_TYPES)
    incoming_product_id = serializers.CharField(required=False)  # Make the id field read-only
    source_location_details = LocationSerializer(source='source_location', read_only=True)
    destination_location_details = LocationSerializer(source='destination_location', read_only=True)
    backorder_details = serializers.Serializer(source='backorder', read_only=True)
    supplier_details = VendorSerializer(source='supplier', read_only=True)

    class Meta:
        model = IncomingProduct
        fields = ['incoming_product_id', 'receipt_type', 'related_po', 'supplier', 'source_location',
                  'source_location_details', 'incoming_product_items', 'supplier_details',
                  'destination_location', 'destination_location_details', 'status',
                  'is_validated', 'can_edit', 'is_hidden', 'backorder_details']
        read_only_fields = ['date_created', 'date_updated', "source_location_details", "destination_location_details", "supplier_details"]

    def validate(self, data):
        # validation to ensure that the related purchase order is not already linked to another incoming product.
        related_po = data.get('related_po', None)
        if related_po and IncomingProduct.objects.filter(related_po=related_po).exists():
            raise serializers.ValidationError("This purchase order is already linked to another incoming product.")

        # Ensure that the items data is present and valid
        items_data = data.get('incoming_product_items', [])
        if not items_data and not self.instance:
            raise serializers.ValidationError("At least one item is required.")

        if items_data:
            for item in items_data:
                product = item.get('product')
                expected_quantity = item.get('expected_quantity', 0)
                quantity_received = item.get('quantity_received', 0)
                if not product:
                    raise serializers.ValidationError("Invalid Product")
                if related_po:
                    # Set expected_quantity from the corresponding PO item
                    po_item = related_po.items.filter(product_id=product.id).first()
                    if po_item:
                        if expected_quantity is None:
                            raise serializers.ValidationError("Expected quantity is required if there is no related "
                                                              "purchase order.")
                        if po_item and expected_quantity != po_item.qty:
                            raise serializers.ValidationError("Purchase Order Item quantity mismatch.")
                    else:
                        raise serializers.ValidationError("Product not found in related purchase order items.")
                if quantity_received < 0 or expected_quantity < 0:
                    raise serializers.ValidationError("Quantities cannot be negative.")
        # Ensure that the receipt type is one of the allowed types
        receipt_type = data.get('receipt_type')
        # INCOMING_PRODUCT_RECEIPT_TYPES may be a list of tuples, so extract the valid values
        valid_receipt_types = [choice[0] if isinstance(choice, tuple) else choice for choice in INCOMING_PRODUCT_RECEIPT_TYPES]
        if receipt_type and receipt_type not in valid_receipt_types:
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

        return data

    def create(self, validated_data):
        """
        Create a new Incoming Product with its associated items.
        """
        items_data = validated_data.pop('incoming_product_items')
        related_po = validated_data.get('related_po', None)
        incoming_product = IncomingProduct.objects.create(**validated_data)
        location = validated_data['destination_location']
        for item_data in items_data:
            product = item_data.get('product')
            quantity_received = item_data.get('quantity_received', 0)
            ip_item = IncomingProductItem.objects.create(incoming_product=incoming_product, **item_data)
            if not ip_item:
                raise serializers.ValidationError("Failed to create Incoming Product Item.")
            # Update product quantity if validated
            if incoming_product.status == "validated":
                location_stock, created = LocationStock.objects.get_or_create(
                    location=location, product=product,
                    defaults={'quantity': 0}
                )
                if location_stock:
                    location_stock.quantity += quantity_received
                    location_stock.save()
                else:
                    raise serializers.ValidationError(
                        "Product does not exist in the specified warehouse location."
                    )
        # Always return the model instance
        return incoming_product

    def update(self, instance, validated_data):
        """
        Update an existing instance with validated data.
        """
        items_data = validated_data.pop('incoming_product_items', None)
        related_po = validated_data.get('related_po', getattr(instance, 'related_po', None))
        destination_location = validated_data.get('destination_location', instance.destination_location)
        partial = self.context.get('partial', False)
        status = validated_data.get('status', None)
        was_validated = instance.status == 'validated'
        is_now_validated = status == 'validated'

        if was_validated:
            raise serializers.ValidationError(
                "Incoming Product cannot be updated once the status is set to 'validated'."
            )

        # Update the instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data:
            existing_items = {item.id: item for item in instance.incoming_product_items.all()}
            incoming_item_ids = set(item_data.get('id') for item_data in items_data if item_data.get('id'))

            if partial:
                # Only update or add provided items, do not delete others
                for item_data in items_data:
                    item_id = item_data.get('id')
                    if item_id and item_id in existing_items:
                        ip_item = existing_items[item_id]
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(ip_item, attr, value)
                        ip_item.save()
                    else:
                        IncomingProductItem.objects.create(incoming_product=instance, **item_data)
            else:
                # Full update: delete items not present, update/add others
                for item_id in set(existing_items.keys()) - incoming_item_ids:
                    existing_items[item_id].delete()
                for item_data in items_data:
                    item_id = item_data.get('id')
                    if item_id and item_id in existing_items:
                        ip_item = existing_items[item_id]
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(ip_item, attr, value)
                        ip_item.save()
                    else:
                        IncomingProductItem.objects.create(incoming_product=instance, **item_data)
            # # Clear existing items and add new ones
            # instance.incoming_product_items.all().delete()
            # for item_data in items_data:
            #     product = item_data.get('product')
            #     expected_quantity = item_data.get('expected_quantity', None)
            #     quantity_received = item_data.get('quantity_received', 0)
            #     # Set expected_quantity from PO if related_po exists
            #     if related_po:
            #         po_item = related_po.items.filter(product_id=product.id).first()
            #         if po_item:
            #             item_data['expected_quantity'] = po_item.qty
            #         else:
            #             raise serializers.ValidationError("Product not found in related purchase order items.")
            #     else:
            #         item_data['expected_quantity'] = expected_quantity
            #     ip_item = IncomingProductItem.objects.create(incoming_product=instance, **item_data)
            #     if not ip_item:
            #         raise serializers.ValidationError("Failed to create Incoming Product Item.")
                # Update product quantity if validated
                # Only update stock if the status is being changed to validated in this update

        if not was_validated and is_now_validated:
            for item in instance.incoming_product_items.all():
                product = item.product
                quantity_received = item.quantity_received
                location_stock, created = LocationStock.objects.get_or_create(
                    location=destination_location, product=product,
                    defaults={'quantity': 0}
                )
                if location_stock:
                    location_stock.quantity += quantity_received
                    location_stock.save()
                else:
                    raise serializers.ValidationError(
                        "Product does not exist in the specified warehouse location."
                    )

        return instance


class BackOrderItemSerializer(serializers.ModelSerializer):
    backorder = serializers.PrimaryKeyRelatedField(read_only=True)
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_hidden=False),
        write_only=True
    )
    product_details = ProductSerializer(source='product', read_only=True)

    class Meta:
        model = BackOrderItem
        fields = ['id', 'backorder', 'product', 'expected_quantity', 'quantity_received', 'product_details']
        read_only_fields = ['id', 'backorder', 'product_details']


class BackOrderNotCreateSerializer(serializers.ModelSerializer):
    backorder_of = serializers.PrimaryKeyRelatedField(
        read_only=True,  # This field is read-only in this serializer
    )
    backorder_items = BackOrderItemSerializer(many=True)
    backorder_of_details = IncomingProductSerializer(source='backorder_of', read_only=True)

    class Meta:
        model = BackOrder
        fields = ['backorder_id', 'backorder_of', 'backorder_of_details', 'backorder_items', 'source_location',
                  'destination_location', 'supplier', 'status', 'receipt_type', 'date_created']
        read_only_fields = ['date_created', 'date_updated']

    def validate(self, attrs):
        # if not attrs.get('backorder_of'):
        #     raise serializers.ValidationError("Back Order must be linked to an Incoming Product.")
        items_data = attrs.get('backorder_items', [])
        if not items_data:
            raise serializers.ValidationError("At least one item is required to create a Back Order.")
        for item in items_data:
            product = item.get('product')
            expected_quantity = item.get('expected_quantity', 0)
            quantity_received = item.get('quantity_received', 0)
            if not product:
                raise serializers.ValidationError("Invalid Product")
            if expected_quantity < 0 or quantity_received < 0:
                raise serializers.ValidationError("Quantities cannot be negative.")
        receipt_type = attrs.get('receipt_type')
        valid_receipt_types = [choice[0] if isinstance(choice, tuple)
                               else choice for choice in INCOMING_PRODUCT_RECEIPT_TYPES]
        if receipt_type not in valid_receipt_types:
            raise serializers.ValidationError(
                "Invalid receipt type. Must be one of: " + ", ".join(str(v) for v in valid_receipt_types)
            )
        if not attrs.get('supplier'):
            raise serializers.ValidationError("Supplier is required.")
        if not attrs.get('source_location'):
            raise serializers.ValidationError("Source location is required.")
        if not attrs.get('destination_location'):
            raise serializers.ValidationError("Destination location is required.")
        return attrs

    def update(self, instance, validated_data):
        items_data = validated_data.pop('backorder_items', None)
        destination_location = validated_data.get('destination_location', instance.destination_location)
        partial = self.context.get('partial', False)
        status = validated_data.get('status', None)
        was_validated = instance.status == 'validated'
        is_now_validated = status == 'validated'
        if was_validated:
            raise serializers.ValidationError(
                "BackOrder cannot be updated once the status is set to 'validated'."
            )
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data:
            existing_items = {item.id: item for item in instance.backorder_items.all()}
            incoming_item_ids = set(item_data.get('id') for item_data in items_data if item_data.get('id'))
            if partial:
                for item_data in items_data:
                    item_id = item_data.get('id')
                    if item_id and item_id in existing_items:
                        bo_item = existing_items[item_id]
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(bo_item, attr, value)
                        bo_item.save()
                    else:
                        BackOrderItem.objects.create(backorder=instance, **item_data)
            else:
                for item_id in set(existing_items.keys()) - incoming_item_ids:
                    existing_items[item_id].delete()
                for item_data in items_data:
                    item_id = item_data.get('id')
                    if item_id and item_id in existing_items:
                        bo_item = existing_items[item_id]
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(bo_item, attr, value)
                        bo_item.save()
                    else:
                        BackOrderItem.objects.create(backorder=instance, **item_data)
        if not was_validated and is_now_validated:
            for item in instance.backorder_items.all():
                product = item.product
                quantity_received = item.quantity_received
                location_stock, created = LocationStock.objects.get_or_create(
                    location=destination_location, product=product,
                    defaults={'quantity': 0}
                )
                if location_stock:
                    location_stock.quantity += quantity_received
                    location_stock.save()
                else:
                    raise serializers.ValidationError(
                        "Product does not exist in the specified warehouse location."
                    )
        return instance

class BackOrderCreateSerializer(serializers.Serializer):
    response = serializers.BooleanField(default=False, write_only=True)
    incoming_product = serializers.PrimaryKeyRelatedField(
        queryset=IncomingProduct.objects.filter(is_hidden=False),
        required=True,
        help_text="ID of the Incoming Product to confirm back order for."
    )

    def validate(self, attrs):
        if 'response' not in attrs:
                raise serializers.ValidationError("Response is required.")
        if not attrs.get('incoming_product'):
            raise serializers.ValidationError("Incoming Product ID is required.")
        incoming_product = attrs.get('incoming_product')
        if not IncomingProduct.objects.filter(pk=incoming_product.pk).exists():
            raise serializers.ValidationError("IncomingProduct does not exist.")
        if BackOrder.objects.filter(backorder_of=incoming_product).exists():
            raise serializers.ValidationError("A back order already exists for this Incoming Product.")
        return attrs

    def create_backorder(self, incoming_product: IncomingProduct):
        items = incoming_product.incoming_product_items.all()
        equal_check = [item.expected_quantity == item.quantity_received for item in items]
        if all(equal_check):
            raise serializers.ValidationError("All items have been fully received. No backorder needed.")
        backorder = BackOrder.objects.create(
            backorder_of=incoming_product,
            source_location=incoming_product.source_location,
            destination_location=incoming_product.destination_location,
            supplier=incoming_product.supplier,
            status='draft',
            receipt_type=incoming_product.receipt_type,
        )
        for item in items:
            if item.quantity_received == item.expected_quantity:
                continue
            adjusted_quantity = item.expected_quantity - item.quantity_received
            BackOrderItem.objects.create(
                backorder=backorder,
                product=item.product,
                expected_quantity=adjusted_quantity,
                quantity_received=adjusted_quantity
            )
        return backorder

    def create(self, validated_data):
        response = validated_data.get('response')
        incoming_product = validated_data.get('incoming_product')
        if not incoming_product:
            raise serializers.ValidationError("Incoming_product is required.")
        if response:
            backorder = self.create_backorder(incoming_product)
            return {"message": "Back Order created successfully.", "backorder_id": backorder.pk}
        else:
            for item in incoming_product.incoming_product_items.all():
                item.expected_quantity = item.quantity_received
                item.save()
            return {"message": "Incoming Product quantities corrected to received quantities."}


# START THE DELIVERY ORDERS
class DeliveryOrderItemSerializer(serializers.ModelSerializer):
    delivery_order = serializers.PrimaryKeyRelatedField(read_only=True)
    product_details = ProductSerializer(source='product_item', read_only=True)
    product_item = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_hidden=False), write_only=True)

    class Meta:
        model = DeliveryOrderItem
        fields = ["id", "product_item", "unit_price", "total_price", "product_details", "quantity_to_deliver", "date_created", "delivery_order", "is_available"]
        read_only_fields = ["id", "product_details", "delivery_order", "total_price"]


class DeliveryOrderSerializer(serializers.ModelSerializer):
    delivery_order_items = DeliveryOrderItemSerializer(many=True)
    order_unique_id = serializers.CharField(read_only=True)
    id = serializers.IntegerField(read_only=True)
    source_location_details = LocationSerializer(source='source_location', read_only=True)

    class Meta:
        model = DeliveryOrder
        fields = ['id', 'order_unique_id', 'customer_name', 'source_location', 'source_location_details',
                  'delivery_address', 'delivery_date', 'shipping_policy', 
                  'return_policy', 'assigned_to', 'delivery_order_items', 'status', 'date_created']

    def validate(self, attrs):
        # Ensure that the delivery order has at least one item
        if not attrs.get('delivery_order_items'):
            raise serializers.ValidationError("At least one delivery order item is required.")
        if not attrs.get('source_location'):
            raise serializers.ValidationError("Source location is required.")
        if attrs.get('delivery_date') < datetime.now().date():
            raise serializers.ValidationError("Delivery date cannot be in the past.")
        # Validate each delivery order item
        for item in attrs['delivery_order_items']:
            product = item.get('product_item')
            quantity = item.get('quantity_to_deliver', 0)
            if not product or not Product.objects.filter(id=product.id, is_hidden=False).exists():
                raise serializers.ValidationError("Invalid Product")
            if quantity <= 0:
                raise serializers.ValidationError("Quantity to deliver must be greater than zero.")

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        products_data = validated_data.pop('delivery_order_items')
        try:
            delivery_order = DeliveryOrder.objects.create(**validated_data)
            delivery_order_items = []
            source_location = delivery_order.source_location
            for product_data in products_data:
                product = product_data.get('product_item')
                quantity_to_deliver = product_data.get('quantity_to_deliver', 0)
                one_item = DeliveryOrderItem(delivery_order=delivery_order, **product_data)
                delivery_order_items.append(one_item)
                # Update product quantity if done
                # if delivery_order.status == "done":
                #     location_stock = LocationStock.objects.filter(
                #         location=source_location, product=product,
                #     ).first()
                #     if location_stock:
                #         location_stock.quantity -= quantity_to_deliver
                #         location_stock.save()
                #     else:
                #         raise serializers.ValidationError(
                #             "Product does not exist in the specified warehouse location."
                #         )
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

        existing_products = {prod.id: prod for prod in instance.delivery_order_items.all()}
        sent_product_ids = []
        source_location = validated_data.get('source_location', instance.source_location)
        try:
            for prod_data in products_data:
                prod_id = prod_data.get('id', None)
                product = prod_data.get('product_item')
                quantity_to_deliver = prod_data.get('quantity_to_deliver', 0)
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
                # Only update stock if the status is being changed to validated in this update
                was_validated = getattr(instance, 'status', None) == 'done'
                is_now_validated = validated_data.get('status', None) == 'done'
                if not was_validated and is_now_validated:
                    location_stock = LocationStock.objects.filter(
                        location=instance.source_location, product=product
                    ).first()
                    if location_stock:
                        location_stock.quantity -= quantity_to_deliver
                        location_stock.save()
                    else:
                        raise serializers.ValidationError(
                            "Product does not exist in the specified warehouse location."
                        )
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
    return_warehouse_location_details = LocationSerializer(source='return_warehouse_location', read_only=True)

    class Meta:
        model = DeliveryOrderReturn
        fields = [
            'unique_record_id',
            'source_document',
            'date_of_return',
            'source_location',
            'return_warehouse_location',
            'return_warehouse_location_details',
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
            create_delivery_order_returns_stock_move(delivery_order_return)

            """This is to update by adding the Quantity returned to the inventory"""
            delivery_order_return_items = DeliveryOrderReturnItem.objects.filter(delivery_order_return_id=delivery_order_return.id)
            for item in delivery_order_return_items:
                # Update product quantity if done
                location_stock = LocationStock.objects.filter(
                    location=delivery_order_return.source_location, product_id=item.returned_product_item,
                ).first()
                if location_stock:
                    location_stock.quantity -= item.returned_quantity
                    location_stock.save()
                else:
                    raise serializers.ValidationError(
                        "Product does not exist in the specified warehouse location."
                    )
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


# START STOCK MOVE
class StockMoveSerializer(serializers.ModelSerializer):
    date_created = serializers.DateTimeField(read_only=True)
    date_moved = serializers.DateTimeField(read_only=True)
    product = ProductSerializer(read_only=True, many=False)
    class Meta:
        model = StockMove
        fields = ["id", "product", "quantity", "source_document_id",
                  "source_location", "destination_location", "date_created", "date_moved"]
# END STOCK MOVE


class InternalTransferItemSerializer(serializers.ModelSerializer):
    internal_transfer = serializers.ReadOnlyField(source="internal_transfer.pk")
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_hidden=False),
        write_only=True
    )
    product_details = ProductSerializer(source='product', read_only=True)

    class Meta:
        model = InternalTransferItem
        fields = ['id', 'product', 'product_details', 'quantity_requested', 'internal_transfer']
        read_only_fields = ['id', 'product_details']


class InternalTransferSerializer(GenericModelSerializer):
    internal_transfer_items = InternalTransferItemSerializer(many=True)
    source_location = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.filter(is_hidden=False),
    )
    destination_location = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.filter(is_hidden=False),
    )
    source_location_details = LocationSerializer(source='source_location', read_only=True)
    destination_location_details = LocationSerializer(source='destination_location', read_only=True)

    class Meta:
        model = InternalTransfer
        fields = ['id', 'internal_transfer_items', 'source_location', 'source_location_details',
                  'destination_location', 'destination_location_details', 'status', 'date_created',
                  'date_updated', 'created_by', 'updated_by', 'is_hidden']
        read_only_fields = ['id', 'date_created', 'date_updated', 'created_by', 'updated_by']

    def validate(self, data):
        if not self.instance:
            if not data.get('internal_transfer_items'):
                raise serializers.ValidationError("At least one item is required for the transfer.")
            items_data = data.get('internal_transfer_items', [])
            if data.get('status') != 'draft':
                for item_data in items_data:
                    product = item_data.get('product')
                    quantity_requested = item_data.get('quantity_requested', 0)
                    if not product or not Product.objects.filter(id=product, is_hidden=False).exists():
                        raise serializers.ValidationError("Invalid Product")
                    if LocationStock.objects.filter(product=product, location=data['source_location']).count() < quantity_requested:
                        raise serializers.ValidationError("Insufficient stock for the product in the source location.")
                    if quantity_requested <= 0:
                        raise serializers.ValidationError("Quantity requested must be greater than zero.")
            if not data.get('source_location'):
                raise serializers.ValidationError("Source location is required.")
            if not data.get('destination_location'):
                raise serializers.ValidationError("Destination location is required.")
            user = self.context['request'].user
            try:
                tenant_user = TenantUser.objects.get(user_id=user.id, is_hidden=False)
            except TenantUser.DoesNotExist:
                raise serializers.ValidationError({'created_by': 'Logged in user is not a valid tenant member.'})
            store_keeper = None
            location_manager = None
            if 'source_location' in data:
                source_location_pk = data.get('source_location', None)
                try:
                    source_location_obj = Location.objects.get(pk=source_location_pk)
                    store_keeper = source_location_obj.store_keeper.pk if source_location_obj.store_keeper else None
                    location_manager = source_location_obj.location_manager.pk if source_location_obj.location_manager else None
                except Location.DoesNotExist:
                    raise serializers.ValidationError("Source location does not exist.")
                except store_keeper is None:
                    raise serializers.ValidationError("Source location does not have a store keeper assigned.")
                except location_manager is None:
                    raise serializers.ValidationError("Source location does not have a location manager assigned.")
                # Check if the store_keeper is the same as the current user
                if (store_keeper and store_keeper == tenant_user.pk) or (
                        location_manager and location_manager == tenant_user.pk):
                    raise serializers.ValidationError(
                        "You do not have permission to transfer items from your own location.")
            if data['source_location'] == data['destination_location']:
                raise serializers.ValidationError("Source and destination locations cannot be the same.")
        return data

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('internal_transfer_items')
        internal_transfer = InternalTransfer.objects.create(**validated_data)
        try:
            InternalTransferItem.objects.bulk_create(
                [InternalTransferItem(internal_transfer=internal_transfer, **item_data) for item_data in items_data]
            )
        except IntegrityError as e:
            raise serializers.ValidationError({"detail": "Error creating internal transfer items: " + str(e)})

        status = validated_data.get('status', 'draft')
        if status not in ['draft', 'awaiting_approval']:
            raise serializers.ValidationError("Internal Transfer status can not be validated on creation.")
        return internal_transfer

    # def make_gradual_status_change(self, instance, status):
    #     status_choices = ['draft', 'awaiting_approval', 'released', 'done',]
    #     if status not in status_choices:
    #         raise serializers.ValidationError(f"Invalid status: {status}. Must be one of {status_choices}.")
    #     # Ensure the status change is gradual
    #     current_status_index = status_choices.index(instance.status)
    #     new_status_index = status_choices.index(status)
    #     if new_status_index - current_status_index != 1:
    #         raise serializers.ValidationError(
    #             f"Cannot change status from {instance.status} to {status}. Status changes must be gradual."
    #         )


    def update(self, instance, validated_data):
        items_data = validated_data.pop('internal_transfer_items', None)
        partial = self.context.get('partial', False)
        status = validated_data.get('status', None)
        was_validated = instance.status == 'done'
        was_cancelled = instance.status == 'cancelled'
        is_now_validated = status == 'done'

        if was_cancelled and (status and status != 'draft'):
            raise serializers.ValidationError(
                "Internal Transfer cannot be updated once the status is set to 'cancelled'. Reset to Draft first."
            )
        if was_validated:
            raise serializers.ValidationError(
                "Internal Transfer cannot be updated once the status is set to 'done'."
            )

        # Update the instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data:
            existing_items = {item.id: item for item in instance.internal_transfer_items.all()}
            internal_item_ids = set(item_data.get('id') for item_data in items_data if item_data.get('id'))

            if partial:
                # Only update or add provided items, do not delete others
                for item_data in items_data:
                    item_id = item_data.get('id')
                    if item_id and item_id in existing_items:
                        it_item = existing_items[item_id]
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(it_item, attr, value)
                        it_item.save()
                    else:
                        InternalTransferItem.objects.create(internal_transfer=instance, **item_data)
            else:
                # Full update: delete items not present, update/add others
                for item_id in set(existing_items.keys()) - internal_item_ids:
                    existing_items[item_id].delete()
                for item_data in items_data:
                    item_id = item_data.get('id')
                    if item_id and item_id in existing_items:
                        it_item = existing_items[item_id]
                        for attr, value in item_data.items():
                            if attr != 'id':
                                setattr(it_item, attr, value)
                        it_item.save()
                    else:
                        InternalTransferItem.objects.create(internal_transfer=instance, **item_data)

        if not was_validated and is_now_validated:
            for item in instance.internal_transfer_items.all():
                product = item.product
                quantity_requested = item.quantity_requested
                source_stock = LocationStock.objects.get(location=instance.source_location, product=product)
                destination_stock, created = LocationStock.objects.get_or_create(
                    location=instance.destination_location, product=product,
                    defaults={'quantity': 0}
                )
                if source_stock and destination_stock:
                    source_stock.quantity -= quantity_requested
                    destination_stock.quantity += quantity_requested
                    source_stock.save()
                    destination_stock.save()
                else:
                    raise serializers.ValidationError(
                        "Product does not exist in the specified warehouse location."
                    )
        return instance