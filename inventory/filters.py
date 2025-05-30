import django_filters
from .models import StockMove

class StockMoveFilter(django_filters.FilterSet):
    date_from = django_filters.DateTimeFilter(field_name='date_moved', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='date_moved', lookup_expr='lte')
    source_location = django_filters.NumberFilter(field_name='source_location__id')
    destination_location = django_filters.NumberFilter(field_name='destination_location__id')
    product = django_filters.NumberFilter(field_name='product__id')

    class Meta:
        model = StockMove
        fields = ['date_from', 'date_to', 'source_location', 'destination_location', 'product']
