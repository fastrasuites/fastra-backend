from inventory.models import Location
from purchase.models import Product, Vendor, Currency
from users.models import TenantUser
from users.serializers import TenantUserSerializer
from .models import GenericModel

from rest_framework import serializers

# Used for patches and updates
class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'

class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'

class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = '__all__'


class GenericModelSerializer(serializers.ModelSerializer):
    """
    A base serializer that can be used to create generic serializers.
    """
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    updated_by = serializers.PrimaryKeyRelatedField(read_only=True)
    date_created = serializers.DateTimeField(read_only=True)
    date_updated = serializers.DateTimeField(read_only=True)
    created_by_details = TenantUserSerializer(source='created_by', read_only=True)
    updated_by_details = TenantUserSerializer(source='updated_by', read_only=True)
    is_hidden = serializers.BooleanField(default=False)

    class Meta:
        fields = (
            'created_by', 'updated_by',
            'date_created', 'date_updated',
            'is_hidden', 'created_by_details', 'updated_by_details'
        )
        # ⚠️ no `model = GenericModel` and no `abstract = True`
