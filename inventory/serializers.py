from rest_framework import serializers

from purchase.models import Product
from users.models import TenantUser

from .models import (Location, MultiLocation, StockAdjustment, StockAdjustmentItem,
                     Scrap, ScrapItem)


class LocationSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='location-detail')
    location_manager = serializers.HyperlinkedRelatedField(queryset=TenantUser.objects.filter(is_hidden=False),
                                                           view_name='tenant-user-detail')
    store_keeper = serializers.HyperlinkedRelatedField(queryset=TenantUser.objects.filter(is_hidden=False),
                                                       view_name='tenant-user-detail')

    class Meta:
        model = Location
        fields = ['url', 'id', 'location_code', 'location_name', 'location_type', 'address', 'location_manager',
                  'store_keeper', 'contact_information', 'is_hidden']
        read_only_fields = ['date_created']

class MultiLocationSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='multi-location-detail')

    class Meta:
        model = MultiLocation
        fields = ['url', 'is_activated']


class StockAdjustmentItemSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='stock-adjustment-item-detail')
    stock_adjustment = serializers.HyperlinkedRelatedField(queryset=StockAdjustment.objects.filter(is_hidden=False),
                                                           view_name='stock-adjustment-detail')
    product = serializers.HyperlinkedRelatedField(queryset=Product.objects.filter(is_hidden=False),
                                                  view_name='product-detail')

    class Meta:
        model = StockAdjustmentItem
        fields = ['url', 'id', 'product', 'unit_of_measure', 'current_quantity', 'adjusted_quantity',
                  'stock_adjustment']


class StockAdjustmentSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='stock-adjustment-detail')
    warehouse_location = serializers.HyperlinkedRelatedField(queryset=Location.objects.filter(is_hidden=False),
                                                             view_name='location-detail')

    items = StockAdjustmentItemSerializer(many=True, read_only=True)

    class Meta:
        model = StockAdjustment
        fields = ['url', 'id', 'adjustment_type', 'warehouse_location', 'notes', 'status', 'is_hidden', 'items']
        read_only_fields = ['date_created', 'date_updated']

    def create(self, validated_data):
        """
        Create a new Stock Adjustment with its associated items.
        """
        items_data = validated_data.pop('items')
        if not items_data:
            raise serializers.ValidationError("At least one item is required to create a Stock Adjustment.")
        stock_adjustment = StockAdjustment.objects.create(**validated_data)
        for item_data in items_data:
            StockAdjustmentItem.objects.create(stock_adjustment=stock_adjustment, **item_data)
            # Update the product's quantity'
            product = item_data.get('product')
            product.current_quantity = item_data.get('adjusted_quantity')
            product.save()
        return stock_adjustment


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
