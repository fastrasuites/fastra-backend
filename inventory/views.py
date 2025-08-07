from datetime import timezone
from decimal import Decimal
import json

from django.db import models
from django.db.utils import IntegrityError
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.mixins import CreateModelMixin
from rest_framework.response import Response
from rest_framework import serializers

from purchase.models import Product
from shared.viewsets.soft_delete_search_viewset import SoftDeleteWithModelViewSet, SearchDeleteViewSet, NoCreateSearchViewSet
from users.module_permissions import HasModulePermission

from .models import (DeliveryOrder, DeliveryOrderItem, DeliveryOrderReturn, DeliveryOrderReturnItem, Location, LocationStock,
                     MultiLocation, ReturnIncomingProduct, ScrapItem, StockAdjustment, Scrap, IncomingProduct,
                     IncomingProductItem, StockMove, BackOrder, BackOrderItem)
from .serializers import (DeliveryOrderReturnItemSerializer, DeliveryOrderReturnSerializer,
                          DeliveryOrderSerializer, LocationSerializer, MultiLocationSerializer,
                          ReturnIncomingProductSerializer, StockAdjustmentSerializer, BackOrderSerializer,
                          ScrapSerializer, IncomingProductSerializer, StockMoveSerializer,
                          BackOrderCreateSerializer)

from .utilities.utils import generate_delivery_order_unique_id, generate_returned_record_unique_id, generate_returned_incoming_product_unique_id
from django.db import transaction
from rest_framework import mixins, viewsets
from .filters import StockMoveFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import ObjectDoesNotExist
from users.config import basic_action_permission_map


class LocationViewSet(SearchDeleteViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    filterset_fields = ['location_name', 'location_type', "location_manager__user_id", "store_keeper__user_id"]
    search_fields = ['id', 'location_name', 'location_type']

    @action(detail=False, methods=['GET'])
    def get_active_locations(self, request):
        queryset = Location.get_active_locations()
        return Response(queryset.values())

    @action(detail=True, methods=['GET'])
    def location_stock_levels(self, request, *args, **kwargs):
        """
        Returns the stock levels for all products in a specific location.
        """
        try:
            location = self.get_object()
            if location.is_hidden:
                return Response({"error": "Location is archived."}, status=status.HTTP_404_NOT_FOUND)
            stock_levels = location.get_stock_levels()
            return Response(stock_levels, status=status.HTTP_200_OK)
        except ObjectDoesNotExist:
            return Response({"error": "Location not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        try:
            if not MultiLocation.objects.filter(is_activated=True).exists() and len(Location.get_active_locations()) >= 1:
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
    app_label = "inventory"
    model_name = "stockadjustment"
    permission_classes = [permissions.IsAuthenticated, HasModulePermission]
    lookup_field = 'id'
    lookup_url_kwarg = 'id'
    filterset_fields = ['date_created', 'status', "warehouse_location__id"]
    search_fields = ['date_created', 'status', "warehouse_location__location_name", "stock_adjustment_items__product__product_name"]
    action_permission_map = {
        **basic_action_permission_map,
        "check_editable": "view",
        "draft_list": "view",
        "done_list": "view",          
    }

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


class ScrapViewSet(SearchDeleteViewSet):
    queryset = Scrap.objects.all()
    serializer_class = ScrapSerializer
    app_label = "inventory"
    model_name = "scrap"
    permission_classes = [permissions.IsAuthenticated, HasModulePermission]
    filterset_fields = ['date_created', 'status', "warehouse_location__id", 'adjustment_type']
    search_fields = ['date_created', 'status', "warehouse_location__location_name", 'adjustment_type', 'scrap_items__product__product_name']
    lookup_field = 'id'
    lookup_url_kwarg = 'id'
    action_permission_map = {
        **basic_action_permission_map,
        "check_editable": "view"
    }


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


    def partial_update(self, request, *args, **kwargs):
        try:
            data = request.data
            instance = self.get_object()

            instance.adjustment_type = data.get("adjustment_type", instance.adjustment_type) or instance.adjustment_type
            instance.warehouse_location_id = data.get("warehouse_location", instance.warehouse_location)
            instance.notes = data.get("notes", instance.notes)
            instance.status = data.get("status", instance.status)
            instance.can_edit = data.get("can_edit", instance.can_edit)
            instance.is_done = data.get("is_done", instance.is_done)

            with transaction.atomic():
                items = data.get("scrap_items", [])
                if items:
                    for item in items:
                        try:
                            item_id = item.get('id', None)
                            if item_id and ScrapItem.objects.filter(id=item_id, scrap_id=instance.id).exists():
                                item_data = ScrapItem.objects.get(id=item_id, scrap_id=instance.id)
                                item_data.product_id = item["product"]
                                item_data.scrap_quantity = item["scrap_quantity"]
                                item_data.save()
                            else:
                                ScrapItem.objects.create(
                                    scrap_id=instance.id,
                                    product_id=item["product"],
                                    scrap_quantity=item["scrap_quantity"],
                                )
                        except KeyError as ke:
                            return Response(
                                {"error": f"Missing field in scrap item: {str(ke)}"},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        except ObjectDoesNotExist:
                            return Response(
                                {"error": f"One or all of the Products does not exist"},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        except Exception as e:
                            return Response(
                                {"error": f"Error processing delivery order item: {str(e)}"},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                instance.save()

            return_serializer = ScrapSerializer(instance, many=False, context={'request': request})
            return Response(return_serializer.data, status=status.HTTP_200_OK)

        except ObjectDoesNotExist:
            return Response({"error": "Object not found."}, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError as e:
            return Response({"error": f"Database integrity error: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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


class IncomingProductViewSet(SearchDeleteViewSet):
    queryset = IncomingProduct.objects.all()
    serializer_class = IncomingProductSerializer
    app_label = "inventory"
    model_name = "incomingproduct"
    permission_classes = [permissions.IsAuthenticated, HasModulePermission]
    search_fields = ['status', "supplier__company_name", "incoming_product_items__product__product_name", "source_location__location_name", "destination_location__location_name", "incoming_product_id"]
    filterset_fields = ['date_created', 'status', "destination_location__id"]
    lookup_field = 'incoming_product_id'
    lookup_url_kwarg = 'incoming_product_id'
    action_permission_map = {
        **basic_action_permission_map,
        "check_editable": "view",
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        incoming_product_status = self.request.query_params.get('status')
        if incoming_product_status:
            queryset = queryset.filter(status=incoming_product_status)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            incoming_product = serializer.save()
            # Process receipt to handle backorders
            items_data = request.data.get('incoming_product_items', [])
            for item in items_data:
                expected = Decimal(item['expected_quantity'])
                received = Decimal(item['quantity_received'])
                if received == expected:
                    continue  # Scenario 1: All good
                elif received < expected:
                    # Scenario 2: Less received
                    error = {
                        "IP_ID": str(incoming_product.pk),
                        "error": "Received quantity is less than expected quantity. Create a backorder to compensate for the missing quantity."
                    }
                    raise ValidationError(json.dumps(error), code="backorder_required")
                else:
                    # Scenario 3: More received
                    raise serializers.ValidationError(
                        "Received quantity exceeds expected quantity. "
                        "You can choose to pay or issue a return for the excess quantity."
                    )
            response_data = serializer.data
            return Response(response_data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['get'], detail=True)
    def get_backorder(self, request, pk=None):
        """Get the backorder for a specific incoming product."""
        try:
            incoming_product = self.get_object()
            backorder = BackOrder.objects.filter(backorder_of=incoming_product).first()
            if not backorder:
                return Response({"detail": "No backorder found for this incoming product."}, status=status.HTTP_404_NOT_FOUND)
            serializer = BackOrderSerializer(backorder, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ObjectDoesNotExist:
            return Response({"detail": "Incoming product not found."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def check_editable(self, request, *args, **kwargs):
        """Check if the incoming product is editable (not validated)."""
        incoming_product = self.get_object()
        if not incoming_product.can_edit:
            return Response(
                {'error': 'This incoming product has already been submitted and cannot be edited.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response({'status': 'editable'}, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        try:
            data = request.data
            instance = self.get_object()

            instance.receipt_type = data.get("receipt_type", instance.receipt_type) or instance.receipt_type
            instance.related_po_id = data.get("related_po", instance.related_po_id)
            instance.supplier_id = data.get("supplier", instance.supplier_id)
            instance.source_location_id = data.get("source_location", instance.source_location_id)
            instance.destination_location_id = data.get("destination_location", instance.destination_location_id)
            instance.status = data.get("status", instance.status)

            with transaction.atomic():
                items = data.get("incoming_product_items", [])
                if items:
                    for item in items:
                        try:
                            item_id = item.get('id', None)
                            if item_id and IncomingProductItem.objects.filter(id=item_id, incoming_product_id=instance.incoming_product_id).exists():
                                item_data = IncomingProductItem.objects.get(id=item_id, incoming_product_id=instance.incoming_product_id)
                                item_data.product_id = item["product"]
                                item_data.expected_quantity = item["expected_quantity"]
                                item_data.quantity_received = item["quantity_received"]
                                item_data.save()
                            else:
                                IncomingProductItem.objects.create(
                                    incoming_product_id=instance.incoming_product_id,
                                    expected_quantity=item["expected_quantity"],
                                    quantity_received=item["quantity_received"],
                                    product_id=item["product"]
                                )
                        except KeyError as ke:
                            return Response(
                                {"error": f"Missing field in incoming product item: {str(ke)}"},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        except Exception as e:
                            return Response(
                                {"error": f"Error processing incoming product item: {str(e)}"},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                instance.save()

            return_serializer = IncomingProductSerializer(instance, context={'request': request}, many=False)
            return Response(return_serializer.data, status=status.HTTP_200_OK)

        except ObjectDoesNotExist:
            return Response({"error": "Object not found."}, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError as e:
            return Response({"error": f"Database integrity error: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BackOrderViewSet(NoCreateSearchViewSet):
    queryset = BackOrder.objects.all()
    serializer_class = BackOrderSerializer
    app_label = "inventory"
    model_name = "backorder"
    permission_classes = [permissions.IsAuthenticated, HasModulePermission]
    action_permission_map = basic_action_permission_map
    filterset_fields = ["backorder_of__incoming_product_id", 'status', "destination_location__id"]

    # List, retrieve, update, archive handled by SearchDeleteViewSet
    # Remove create method to delegate creation to ConfirmCreateBackOrderViewSet


class ConfirmCreateBackOrderViewSet(viewsets.GenericViewSet, CreateModelMixin):
    queryset = BackOrder.objects.all()
    serializer_class = BackOrderCreateSerializer
    app_label = "inventory"
    model_name = "backorder"
    permission_classes = [permissions.IsAuthenticated, HasModulePermission]
    action_permission_map = basic_action_permission_map

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            back_order = serializer.save()
            return Response(back_order, status=status.HTTP_201_CREATED)
        except IntegrityError as e:
            return Response({"detail": "Error creating back order: " + str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": "An unexpected error occurred: " + str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# class IncomingProductItemViewSet(viewsets.ModelViewSet):
#     queryset = IncomingProductItem.objects.all()
#     serializer_class = IPItemSerializer
#     permission_classes = [permissions.IsAuthenticated]


class MultiLocationViewSet(viewsets.GenericViewSet):
    queryset = MultiLocation.objects.all()
    serializer_class = MultiLocationSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['put', 'patch'])
    def change_status(self, request):
        try:
            instance = self.get_queryset().first()
            if instance.is_activated:
                # Deactivating: check if active locations > 1
                if Location.get_active_locations().filter(is_hidden=False).count() > 1:
                    return Response({
                        'status': 'error',
                        'message': 'Reduce number of locations to three before deactivating'
                    }, status=status.HTTP_400_BAD_REQUEST)
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
class DeliveryOrderViewSet(SoftDeleteWithModelViewSet):
    queryset = DeliveryOrder.objects.filter(is_hidden=False)
    serializer_class = DeliveryOrderSerializer
    app_label = "inventory"
    model_name = "deliveryorder"
    permission_classes = [permissions.IsAuthenticated, HasModulePermission]
    action_permission_map = {
        **basic_action_permission_map,
        "check_availability": "edit",
        "confirm_delivery": "approve"
    }

    def create(self, request, *args, **kwargs):
        """This is to create a new Delivery Order."""
        # Logic to create a new delivery order
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        # Check for duplicates based on relevant fields
        # existing_order = DeliveryOrder.objects.filter(
        #     customer_name=validated_data["customer_name"],
        #     source_location=validated_data["source_location"],
        #     delivery_address=validated_data["delivery_address"],
        #     delivery_date=validated_data["delivery_date"],
        #     shipping_policy=validated_data["shipping_policy"],
        # ).first()
        # if existing_order:
        #     return Response({"detail": "A delivery order with the same details already exists."},
        #                     status=status.HTTP_400_BAD_REQUEST)

        # Generate the unique order ID
        validated_data["order_unique_id"] = generate_delivery_order_unique_id(validated_data["source_location"].id)        

        # Check if products list is empty
        products = validated_data.get('delivery_order_items', [])
        if not products:
            return Response({"detail": "At least one product item is required."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except IntegrityError as e:
            return Response({"detail": "Error creating delivery order: " + str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": "An unexpected error occurred: " + str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def check_availability(self, request, *args, **kwargs):
        """This is to check for the availability of the Product Items in a Delievery Order. Append the delievery order id(pk) to the request"""
        id = kwargs.get('pk')
        all_confirmed = True

        if not DeliveryOrderItem.objects.filter(is_hidden=False, delivery_order_id=id).exists():
            return Response({"detail": "This delivery order does not exist"},
                            status=status.HTTP_400_BAD_REQUEST)
        delivery_order_items = DeliveryOrderItem.objects.filter(is_hidden=False, delivery_order_id=id)
        for item in delivery_order_items:
            if item.product_item.available_product_quantity < item.quantity_to_deliver:
                item.is_available = False
                all_confirmed = False

        delivery_order = DeliveryOrder.objects.filter(is_hidden=False, id=id).first()
        try:
            delivery_order.status = "ready" if all_confirmed else "waiting"
            delivery_order.save()
            serialized_order = DeliveryOrderSerializer(delivery_order, context={'request': request})
            return Response(serialized_order.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": "An error occurred while updating the delivery order status: " + str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @transaction.atomic
    def confirm_delivery(self, request, *args, **kwargs):
        serializer = self.get_serializer
        """This is to confirm the delivery order. Append the delievery order id(pk) to the request"""
        id = kwargs.get('pk')

        delivery_order = DeliveryOrder.objects.filter(is_hidden=False, id=id).first()
        if delivery_order.status.lower().strip() == "done":
            return Response({"detail": "You cannot confirm a delivery order that already have the status of DONE!!!"},
                            status=status.HTTP_400_BAD_REQUEST)
        elif delivery_order.status.lower().strip() != "ready":
            return Response({"detail": "A Delivery Order cannot be Confirmed if the Status is not set to Ready"},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            delivery_order.status = "done"
            delivery_order.save()

            """This is to update by deducting the Quantity to deliver from the available quantity of the Product"""
            delivery_order_items = DeliveryOrderItem.objects.filter(is_hidden=False, delivery_order_id=id)
            for item in delivery_order_items:
                # Update product quantity if done
                location_stock = LocationStock.objects.filter(
                    location=delivery_order.source_location, product_id=item.product_item,
                ).first()
                if location_stock:
                    location_stock.quantity -= item.quantity_to_deliver
                    location_stock.save()
                else:
                    raise serializers.ValidationError(
                        "Product does not exist in the specified warehouse location."
                    )

            serialized_order = DeliveryOrderSerializer(delivery_order, context={'request': request})
            return Response(serialized_order.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": "An error occurred while updating the delivery order status: " + str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def partial_update(self, request, *args, **kwargs):
        try:
            data = request.data
            instance = self.get_object()

            instance.customer_name = data.get("customer_name", instance.customer_name) or instance.customer_name
            instance.source_location_id = data.get("source_location", instance.source_location)
            instance.delivery_address = data.get("delivery_address", instance.delivery_address)
            instance.delivery_date = data.get("delivery_date", instance.delivery_date)
            instance.shipping_policy = data.get("shipping_policy", instance.shipping_policy)
            instance.return_policy = data.get("return_policy", instance.return_policy)
            instance.assigned_to = data.get("assigned_to", instance.assigned_to)

            with transaction.atomic():
                items = data.get("delivery_order_items", [])
                if items:
                    for item in items:
                        try:
                            item_id = item.get('id', None)
                            if item_id and DeliveryOrderItem.objects.filter(id=item_id, delivery_order_id=instance.id).exists():
                                item_data = DeliveryOrderItem.objects.get(id=item_id, delivery_order_id=instance.id)
                                item_data.product_item_id = item["product_item"]
                                item_data.quantity_to_deliver = item["quantity_to_deliver"]
                                item_data.save()
                            else:
                                DeliveryOrderItem.objects.create(
                                    delivery_order_id=instance.id,
                                    product_item_id=item["product_item"],
                                    quantity_to_deliver=item["quantity_to_deliver"],
                                )
                        except KeyError as ke:
                            return Response(
                                {"error": f"Missing field in delivery order item: {str(ke)}"},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        except ObjectDoesNotExist:
                            return Response(
                                {"error": f"One or all of the Products does not exist"},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        except Exception as e:
                            return Response(
                                {"error": f"Error processing delivery order item: {str(e)}"},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                instance.save()

            return_serializer = DeliveryOrderSerializer(instance, many=False, context={'request': request})
            return Response(return_serializer.data, status=status.HTTP_200_OK)

        except ObjectDoesNotExist:
            return Response({"error": "Object not found."}, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError as e:
            return Response({"error": f"Database integrity error: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# END FOR THE DELIVERY ORDER



# START FOR THE DELIVERY ORDER RETURN 
class DeliveryOrderReturnViewSet(SoftDeleteWithModelViewSet):
    queryset = DeliveryOrderReturn.objects.filter(is_hidden=False)
    serializer_class = DeliveryOrderReturnSerializer
    app_label = "inventory"
    model_name = "deliveryorderreturn"
    permission_classes = [permissions.IsAuthenticated, HasModulePermission]
    action_permission_map = basic_action_permission_map

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        delivery_order_id = validated_data.get('source_document').id
        if not delivery_order_id:
            return Response({"detail": "Delivery order ID is required for the source document."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            delivery_order = DeliveryOrder.objects.get(id=delivery_order_id)
        except DeliveryOrder.DoesNotExist:
            return Response({"detail": "Delivery order not found."}, status=status.HTTP_404_NOT_FOUND)
        
        if delivery_order.status != 'done':
            return Response({"detail": "Return can only be processed for orders with status 'Done'."}, status=status.HTTP_400_BAD_REQUEST)
        
        if delivery_order.return_policy and "no returns" in delivery_order.return_policy.lower():
            return Response({"detail": "This order is not eligible for returns."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate product lines:
        returned_product_items = validated_data.get('delivery_order_return_items', [])
        if not returned_product_items or len(returned_product_items) <= 0:
            return Response({"detail": "At least one product line must be provided."}, status=status.HTTP_400_BAD_REQUEST)
        
        for product in returned_product_items:
            if int(product.get('returned_quantity', 0)) <= 0:
                return Response({"detail": "Returned quantity must be greater than zero for all products."}, status=status.HTTP_400_BAD_REQUEST)
            
            if product['returned_quantity'] > product['initial_quantity']:
                return Response({"detail": f"Returned quantity cannot be greater than initial quantity for {product['product_name']}."}, status=status.HTTP_400_BAD_REQUEST)

        # Auto set unique_record_id, source_document, source_location, return_warehouse_location
        validated_data['unique_record_id'] = generate_returned_record_unique_id(delivery_order.order_unique_id)
        validated_data['source_document'] = delivery_order
        validated_data['source_location'] = delivery_order.source_location
        validated_data['return_warehouse_location'] = delivery_order.source_location

        if DeliveryOrderReturn.objects.filter(is_hidden=False, unique_record_id=validated_data['unique_record_id']).exists():
            return Response({"detail": "This record exists."}, status=status.HTTP_400_BAD_REQUEST)        
        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class DeliveryOrderReturnItemViewSet(SoftDeleteWithModelViewSet):
    queryset = DeliveryOrderReturnItem.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DeliveryOrderReturnItemSerializer
# END FOR THE DELIVERY ORDER RETURN


# START RETURN INCOMING PRODUCTS
class ReturnIncomingProductViewSet(SoftDeleteWithModelViewSet):
    queryset = ReturnIncomingProduct.objects.filter(is_hidden=False)
    serializer_class = ReturnIncomingProductSerializer
    app_label = "inventory"
    model_name = "returnincomingproduct"
    permission_classes = [permissions.IsAuthenticated, HasModulePermission]
    action_permission_map = {
        **basic_action_permission_map,
        "approve": "approve"
    }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        try:
            location_code = validated_data["source_document"].destination_location.location_code
            validated_data['unique_id'] = generate_returned_incoming_product_unique_id(location_code)
            self.perform_create(serializer)
            
            # new_serializer = ReturnIncomingProductWithIncomingProductsSerializer(self.queryset[0], many=False, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def approve(self, request, *args, **kwargs):
        try:
            id = kwargs.get('pk')
            return_incoming_product = ReturnIncomingProduct.objects.filter(is_hidden=False, unique_id=id).first()
            if return_incoming_product is None:
                return Response({'detail': "There are no records to approve in the return incoming product"}, status=status.HTTP_400_BAD_REQUEST)
            if return_incoming_product.is_approved:
                return Response({'detail': "You cannot approve an Approved return incoming product record"}, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                return_incoming_product.is_approved = True
                return_incoming_product.save()

                return_serializer = ReturnIncomingProductSerializer(return_incoming_product, many=False, context={'request': request})
                return_incoming_product_items = return_serializer.data.pop("return_incoming_product_items")
                product_list = []
                for item in return_incoming_product_items:
                    # This is where we deduct the returned quantity from the available quantity and then update the database. 
                    product = Product.objects.filter(is_hidden=False, id=item["id"]).first()
                    product.available_product_quantity -= item["quantity_to_be_returned"]
                    product_list.append(product)
                Product.objects.bulk_update(product_list, fields=["available_product_quantity"])

            serializer =  ReturnIncomingProductSerializer(return_incoming_product, many=False, context={'request': request})                    
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
# END RETURN INCOMING PRODUCTS



# START STOCK MOVES
class StockMoveViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    queryset = StockMove.objects.all()
    serializer_class = StockMoveSerializer
    app_label = "inventory"
    model_name = "stockmove"
    permission_classes = [permissions.IsAuthenticated, HasModulePermission]
    filter_backends = [DjangoFilterBackend]
    filterset_class = StockMoveFilter
    action_permission_map = basic_action_permission_map

# END STOCK MOVES
