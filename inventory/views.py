from datetime import timezone
from django.db import models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from purchase.models import Product
from shared.viewsets.soft_delete_search_viewset import SearchDeleteViewSet

from .models import DeliveryOrder, Location, MultiLocation, ReturnProductLine, ReturnRecord, StockAdjustment, StockAdjustmentItem, ScrapItem, Scrap
from .serializers import DeliveryOrderSerializer, DeliveryOrderWithoutProductsSerializer, LocationSerializer, MultiLocationSerializer, ReturnProductLineSerializer, ReturnRecordSerializer, StockAdjustmentSerializer, \
    StockAdjustmentItemSerializer, ScrapItemSerializer, ScrapSerializer

from .utilities.utils import generate_delivery_order_unique_id, generate_returned_record_unique_id

class LocationViewSet(SearchDeleteViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    lookup_field = 'id'
    search_fields = ['id', 'location_name', 'location_type', 'location_manager__username']

    @action(detail=False, methods=['GET'])
    def get_active_locations(self, request):
        queryset = Location.get_active_locations()
        return Response(queryset.values())

    def create(self, request, *args, **kwargs):
        try:
            if MultiLocation.objects.first().is_activated and Location.get_active_locations() >= 1:
                return Response(
                    {'error': 'Max number of Locations reached.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return super().create(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class StockAdjustmentViewSet(SearchDeleteViewSet):
    queryset = StockAdjustment.objects.all()
    serializer_class = StockAdjustmentSerializer
    lookup_field = 'id'
    lookup_url_kwarg = 'id'
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
    def check_editable(self, request, *args, **kwargs):
        """Check if the stock adjustment is editable (not validated)."""
        stock_adj = self.get_object()
        if not stock_adj.can_edit:
            return Response({'error': 'This stock adjustment has already been submitted and cannot be edited.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': 'editable'}, status=status.HTTP_200_OK)

    # @action(detail=True, methods=['put', 'patch'])
    # def submit(self, request, *args, **kwargs):
    #     pk = self.kwargs.get(self.lookup_url_kwarg, None)
    #     if not pk:
    #         return Response({'error': 'Stock Adjustment ID not provided.'}, status=status.HTTP_400_BAD_REQUEST)
    #
    #     stock_adj = self.get_object()
    #     stock_adj.save()
    #     return Response({'status': 'draft'})
    #
    # @action(detail=True, methods=['put', 'patch'])
    # def final_submit(self, request, *args, **kwargs):
    #     stock_adj = self.get_object()
    #     if not stock_adj.can_edit:
    #         return Response({'error': "It is no longer editable"}, status=status.HTTP_400_BAD_REQUEST)
    #
    #     items_data = stock_adj.stock_adjustment_items
    #     for item_data in items_data:
    #         item_data.product.available_product_quantity = item_data.adjusted_quantity
    #
    #     stock_adj.save()
    #     return Response({'status': 'done'})

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
    lookup_field = 'id'
    lookup_url_kwarg = 'id'

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
    def check_editable(self, request, *args, **kwargs):
        """Check if the scrap is editable (not validated)."""
        scrap = self.get_object()
        if not scrap.can_edit:
            return Response({'error': 'This scrap has already been submitted and cannot be edited.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': 'editable'}, status=status.HTTP_200_OK)

    # @action(detail=True, methods=['post'])
    # def submit(self, request, pk=None):
    #     scrap = self.get_object()
    #
    #     items_data = scrap.scrap_items
    #     for item_data in items_data:
    #         item_data.product.available_product_quantity = item_data.adjusted_quantity
    #
    #     scrap.submit()
    #     return Response({'status': 'draft'})
    #
    # @action(detail=True, methods=['put', 'patch'])
    # def final_submit(self, request, pk=None):
    #     scrap = self.get_object()
    #     editable, message = self.check_editable(scrap)
    #     if not editable:
    #         return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
    #
    #     items_data = scrap.scrap_items
    #     for item_data in items_data:
    #         item_data.product.available_product_quantity = item_data.adjusted_quantity
    #
    #     scrap.final_submit()
    #     return Response({'status': 'done'})


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




# START FOR THE DELIVERY ORDER
class DeliveryOrderViewSet(viewsets.ModelViewSet):
    queryset = DeliveryOrder.objects.filter(is_hidden=False)
    serializer_class = DeliveryOrderSerializer

    def list_without_products(self, request, *args, **kwargs):
        # Retrieve all delivery orders without products
        delivery_orders = self.queryset
        serializer = DeliveryOrderWithoutProductsSerializer(delivery_orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        # Logic to create a new delivery order
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        # Check for duplicates based on relevant fields
        existing_order = DeliveryOrder.objects.filter(
            customer_name=validated_data["customer_name"],
            source_location=validated_data["source_location"],
            destination_location=validated_data["destination_location"],
            delivery_date=validated_data["delivery_date"],
            shipping_policy=validated_data["shipping_policy"],
        ).first()
        if existing_order:
            return Response({"detail": "A delivery order with the same details already exists."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Generate the unique order ID
        validated_data["order_unique_id"] = generate_delivery_order_unique_id(validated_data["source_location"])        

        # Check if products list is empty
        products = validated_data.get('products', [])
        if not products:
            return Response({"detail": "At least one product line is required."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError as e:
            return Response({"detail": "Error creating delivery order: " + str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": "An unexpected error occurred: " + str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def check_availability(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        products = validated_data.get('products', [])
        if not products:
            return Response({"detail": "At least one product line is required."},
                            status=status.HTTP_400_BAD_REQUEST)

        all_confirmed = True
        for product in products:
            # Check if product_name and quantity_to_deliver are provided
            product_name = product.get("product_name")
            quantity_to_deliver = product.get("quantity_to_deliver")

            if not product_name or quantity_to_deliver is None:
                return Response({"detail": "Product name and quantity to deliver are required."},
                                status=status.HTTP_400_BAD_REQUEST)

            checked_product = Product.objects.filter(product_name=product_name, is_hidden=False).first()
            if not checked_product:
                return Response({"detail": f"Product '{product_name}' not found."},
                                status=status.HTTP_404_NOT_FOUND)

            if checked_product.available_product_quantity < quantity_to_deliver:
                product["is_available"] = False
                all_confirmed = False
            else:
                product["is_available"] = True

        # Update the status based on availability
        delivery_order = DeliveryOrder.objects.filter(order_unique_id=validated_data["order_unique_id"], is_hidden=False).first()
        if not delivery_order:
            return Response({"detail": "Delivery order not found."},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            delivery_order.status = "ready" if all_confirmed else "waiting"
            delivery_order.save()
            serialized_order = DeliveryOrderSerializer(delivery_order)
            return Response(serialized_order.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": "An error occurred while updating the delivery order status: " + str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def confirm_delivery(self, request, *args, **kwargs):
        serializer = self.get_serializer
# END FOR THE DELIVERY ORDER



# START FOR THE RETURN RECORD
class ReturnRecordViewSet(viewsets.ModelViewSet):
    queryset = ReturnRecord.objects.filter(is_hidden=False)
    serializer_class = ReturnRecordSerializer

    def create(self, request, *args, **kwargs):
        data = request.data
        delivery_order_id = data.get('delivery_order')
        if not delivery_order_id:
            return Response({"detail": "Delivery order ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            delivery_order = DeliveryOrder.objects.get(id=delivery_order_id)
        except DeliveryOrder.DoesNotExist:
            return Response({"detail": "Delivery order not found."}, status=status.HTTP_404_NOT_FOUND)
        
        if delivery_order.status != 'done':
            return Response({"detail": "Return can only be processed for orders with status 'Done'."}, status=status.HTTP_400_BAD_REQUEST)
        
        if delivery_order.return_policy and "no returns" in delivery_order.return_policy.lower():
            return Response({"detail": "This order is not eligible for returns."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate product lines:
        return_products = data.get('return_products', [])
        if not return_products or len(return_products) <= 0:
            return Response({"detail": "At least one product line must be provided."}, status=status.HTTP_400_BAD_REQUEST)
        
        for product in return_products:
            if int(product.get('returned_quantity', 0)) <= 0:
                return Response({"detail": "Returned quantity must be greater than zero for all products."}, status=status.HTTP_400_BAD_REQUEST)
            
            if product['returned_quantity'] > product['initial_quantity']:
                return Response({"detail": f"Returned quantity cannot be greater than initial quantity for {product['product_name']}."}, status=status.HTTP_400_BAD_REQUEST)

        # Auto set unique_record_id, source_document, source_location, return_warehouse_location
        data['unique_record_id'] = generate_returned_record_unique_id(delivery_order.order_unique_id)
        data['source_document'] = delivery_order.order_unique_id
        data['source_location'] = delivery_order.source_location.id
        data['return_warehouse_location'] = delivery_order.source_location.id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        if ReturnRecord.objects.filter(is_hidden=False, unique_record_id=data['unique_record_id']).exists():
            return Response({"detail": "This record exists."}, status=status.HTTP_400_BAD_REQUEST)        
        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class ReturnProductLineViewSet(viewsets.ModelViewSet):
    queryset = ReturnProductLine.objects.filter(is_hidden=False)
    serializer_class = ReturnProductLineSerializer
# END FOR THE RETURN RECORD