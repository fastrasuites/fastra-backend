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
        model = GenericModel
        fields = ('created_by', 'updated_by', 'date_created', 'date_updated', 'is_hidden', 'created_by_details', 'updated_by_details')
        abstract = True

    def to_internal_value(self, data):
        """
        Override to_internal_value to handle the case where the data is None.
        """
        data = data.copy()
        if data is None:
            return {}
        # add created_by fields if they are not present
        user = self.context['request'].user
        try:
            tenant_user = TenantUser.objects.get(user_id=user.id, is_hidden=False)
            data['created_by'] = tenant_user.pk
        except TenantUser.DoesNotExist:
            data['created_by'] = None
            raise serializers.ValidationError(
                "TenantUser does not exist for the current user."
            )
        return super().to_internal_value(data)

    def update(self, instance, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            user = request.user
            try:
                tenant_user = TenantUser.objects.get(user_id=user.id, is_hidden=False)
                validated_data['updated_by'] = tenant_user.pk
            except TenantUser.DoesNotExist:
                raise serializers.ValidationError(
                    "TenantUser does not exist for the current user."
                )
        return super().update(instance, validated_data)
