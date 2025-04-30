from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from shared.viewsets.soft_delete_search_viewset import SearchDeleteViewSet

from .models import Location, MultiLocation, StockAdjustment, StockAdjustmentItem, ScrapItem, Scrap
from .serializers import LocationSerializer, MultiLocationSerializer, StockAdjustmentSerializer, \
    StockAdjustmentItemSerializer, ScrapItemSerializer, ScrapSerializer


class LocationViewSet(SearchDeleteViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    lookup_field = 'id'
    search_fields = ['id', 'location_name', 'location_type', 'location_manager__username']

    @action(detail=False, methods=['GET'])
    def get_active_locations(self, request):
        queryset = Location.get_active_locations()
        return Response(queryset.values())

class StockAdjustmentViewSet(SearchDeleteViewSet):
    queryset = StockAdjustment.objects.all()
    serializer_class = StockAdjustmentSerializer
    search_fields = ['date_created', 'status', 'warehouse_location']

    def get_queryset(self):
        queryset = super().get_queryset()
        stock_adj_status = self.request.query_params.get('status')
        if stock_adj_status:
            queryset = queryset.filter(status=stock_adj_status)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stock_adj = serializer.save()
        return Response(self.get_serializer(stock_adj).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def check_editable(self, stock_adj):
        """Check if the stock adjustment is editable (not validated)."""
        if stock_adj.is_validated:
            return False, 'This stock adjustment has already been submitted and cannot be edited.'
        return True, ''

    @action(detail=True, methods=['put', 'patch'])
    def submit(self, request, pk=None):
        stock_adj = self.get_object()

        editable, message = self.check_editable(stock_adj)

        if not editable:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

        stock_adj.submit()
        return Response({'status': 'draft'})

    @action(detail=True, methods=['put', 'patch'])
    def final_submit(self, request, pk=None):
        stock_adj = self.get_object()

        items_data = stock_adj.stock_adjustment_items
        for item_data in items_data:
            item_data.product.available_product_quantity = item_data.adjusted_quantity

        stock_adj.final_submit()
        return Response({'status': 'done'})

    @action(detail=False, methods=['get'])
    def draft_list(self, request):
        queryset = StockAdjustment.draft_stock_adjustments.all()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def done_list(self, request):
        queryset = StockAdjustment.done_stock_adjustments.all()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class StockAdjustmentItemViewSet(viewsets.ModelViewSet):
    queryset = StockAdjustmentItem.objects.all()
    serializer_class = StockAdjustmentItemSerializer
    # permission_classes = [permissions.IsAuthenticated]


class ScrapViewSet(SearchDeleteViewSet):
    queryset = Scrap.objects.all()
    serializer_class = ScrapSerializer
    search_fields = ['date_created', 'status', 'warehouse_location']

    def get_queryset(self):
        queryset = super().get_queryset()
        scrap_status = self.request.query_params.get('status')
        if scrap_status:
            queryset = queryset.filter(status=scrap_status)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scrap = serializer.save()
        return Response(self.get_serializer(scrap).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def check_editable(self, scrap):
        """Check if the scrap is editable (not validated)."""
        if scrap.is_validated:
            return False, 'This stock adjustment has already been submitted and cannot be edited.'
        return True, ''

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        scrap = self.get_object()

        items_data = scrap.scrap_items
        for item_data in items_data:
            item_data.product.available_product_quantity = item_data.adjusted_quantity

        scrap.submit()
        return Response({'status': 'draft'})

    @action(detail=True, methods=['put', 'patch'])
    def final_submit(self, request, pk=None):
        scrap = self.get_object()
        editable, message = self.check_editable(scrap)
        if not editable:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

        items_data = scrap.scrap_items
        for item_data in items_data:
            item_data.product.available_product_quantity = item_data.adjusted_quantity

        scrap.final_submit()
        return Response({'status': 'done'})


class ScrapItemViewSet(viewsets.ModelViewSet):
    queryset = ScrapItem.objects.all()
    serializer_class = ScrapItemSerializer
    # permission_classes = [permissions.IsAuthenticated]



class MultiLocationViewSet(viewsets.GenericViewSet):
    queryset = MultiLocation.objects.all()
    serializer_class = MultiLocationSerializer
    # permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['put', 'patch'])
    def change_status(self, request):
        try:
            instance = self.get_queryset().first()
            instance.is_activated = not instance.is_activated
            instance.save()

            return Response({
                'status': 'success',
                'message': f'MultiLocation {"activated" if instance.is_activated else "deactivated"} successfully',
                'is_activated': instance.is_activated
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['GET'])
    def check_status(self, request):
        try:
            instance = self.get_queryset().first()
            return Response({
                'status': 'success',
                'message': 'MultiLocation is ' + ('activated' if instance.is_activated else 'deactivated'),
                'is_activated': instance.is_activated
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)



