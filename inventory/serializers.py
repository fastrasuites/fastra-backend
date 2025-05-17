from rest_framework import serializers

from purchase.models import Product
from users.models import TenantUser

from .models import (Location, MultiLocation, StockAdjustment, StockAdjustmentItem,
                     Scrap, ScrapItem, IncomingProductItem, IncomingProduct)


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

    class Meta:
        model = IncomingProductItem
        fields = ['id', 'incoming_product', 'product', 'unit_of_measure',
                  'expected_quantity', 'quantity_received']


class IncomingProductSerializer(serializers.ModelSerializer):
    incoming_product_items = IPItemSerializer(many=True)

    id = serializers.CharField(required=False, read_only=True)  # Make the id field read-only

    class Meta:
        model = IncomingProduct
        fields = ['id', 'receipt_type', 'related_po', 'supplier', 'source_location', 'incoming_product_items',
                  'destination_location', 'is_validated', 'can_edit', 'is_hidden']
        read_only_fields = ['date_created', 'date_updated']

    def create(self, validated_data):
        """
        Create a new Scrap with its associated items.
        """
        items_data = validated_data.pop('incoming_product_items')
        if not items_data:
            raise serializers.ValidationError("At least one item is required to create an Incoming Product.")
        incoming_product = IncomingProduct.objects.create(**validated_data)
        for item_data in items_data:
            IncomingProductItem.objects.create(incoming_product=incoming_product, **item_data)
        return incoming_product

    def update(self, instance, validated_data):
        """
        Update an existing instance with validated data.
        """
        items_data = validated_data.pop('incoming_product_items', None)
        if items_data:
            # Clear existing items and add new ones
            instance.incoming_product_items.all().delete()
            for item_data in items_data:
                IncomingProductItem.objects.create(incoming_product=instance, **item_data)

        # Update the instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
