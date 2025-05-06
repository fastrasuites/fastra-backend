from rest_framework import serializers

from purchase.models import Product
from users.models import TenantUser

from .models import (Location, MultiLocation, StockAdjustment, StockAdjustmentItem,
                     Scrap, ScrapItem)


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
                                                           lookup_field='id',               # ✅ use 'id' as lookup field
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
        fields = ['url', 'id', 'adjustment_type', 'warehouse_location', 'notes', 'status', 'is_hidden', 'stock_adjustment_items']
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
            # Update the product's quantity'
            # product = item_data.get('product')
            # product.available_product_quantity = item_data.get('adjusted_quantity')
            # product.save()
        return stock_adjustment

    def update(self, instance, validated_data):
        items_data = validated_data.pop('stock_adjustment_items', None)
        # Update the stock adjustment instance
        instance.adjustment_type = validated_data.get('adjustment_type', instance.adjustment_type)
        instance.warehouse_location = validated_data.get('warehouse_location', instance.warehouse_location)
        instance.notes = validated_data.get('notes', instance.notes)
        instance.status = validated_data.get('status', instance.status)
        instance.save()

        if items_data is not None:
            # Clear existing items and create new ones
            instance.items.all().delete()
            for item_data in items_data:
                StockAdjustmentItem.objects.update_or_create(id=item_data.get('id'),
                                                             stock_adjustment=instance,
                                                             defaults=item_data)
                # Update the product's quantity'
                # product = item_data.get('product')
                # product.available_product_quantity = item_data.get('adjusted_quantity')
                # product.save()
        return instance


class ScrapItemSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='scrap-item-detail')
    scrap = serializers.HyperlinkedRelatedField(queryset=Scrap.objects.filter(is_hidden=False),
                                                view_name='scrap-detail')
    product = serializers.HyperlinkedRelatedField(queryset=Product.objects.filter(is_hidden=False),
                                                  view_name='product-detail')

    class Meta:
        model = ScrapItem
        fields = ['url', 'id', 'scrap', 'product', 'scrap_quantity', 'adjusted_quantity']


class ScrapSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='scrap-detail')
    warehouse_location = serializers.HyperlinkedRelatedField(queryset=Location.objects.filter(is_hidden=False),
                                                             view_name='location-detail')

    items = ScrapItemSerializer(many=True, read_only=True)

    class Meta:
        model = Scrap
        fields = ['url', 'id', 'adjustment_type', 'warehouse_location', 'notes', 'status', 'is_hidden', 'items']
        read_only_fields = ['date_created', 'date_updated', 'adjustment_type']

    def create(self, validated_data):
        """
        Create a new Stock Adjustment with its associated items.
        """
        items_data = validated_data.pop('items')
        if not items_data:
            raise serializers.ValidationError("At least one item is required to create a Scrap.")
        scrap = Scrap.objects.create(**validated_data)
        for item_data in items_data:
            ScrapItem.objects.create(scrap=scrap, **item_data)
            # Update the product's quantity'
            product = item_data.get('product')
            product.available_product_quantity = item_data.get('adjusted_quantity')
            product.save()
        return scrap
