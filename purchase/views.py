from django.shortcuts import render
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, generics, filters
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import PurchaseRequest, PurchaseRequestItem, Department, Vendor, Product, RequestForQuotation, \
    RequestForQuotationItem, VendorCategory, ProductCategory, UnitOfMeasure, RFQVendorQuote, RFQVendorQuoteItem, \
    PurchaseOrder, PurchaseOrderItem, POVendorQuote, POVendorQuoteItem
from .serializers import PurchaseRequestSerializer, DepartmentSerializer, VendorSerializer, \
    ProductSerializer, RequestForQuotationSerializer, RequestForQuotationItemSerializer, \
    VendorCategorySerializer, ProductCategorySerializer, UnitOfMeasureSerializer, \
    PurchaseRequestItemSerializer, RFQVendorQuoteSerializer, RFQVendorQuoteItemSerializer, \
    PurchaseOrderSerializer, PurchaseOrderItemSerializer, POVendorQuoteSerializer, \
    POVendorQuoteItemSerializer


class SoftDeleteWithModelViewSet(viewsets.ModelViewSet):
    """
    A viewset that provides default `list()`, `create()`, `retrieve()`, `update()`, `partial_update()`,
    and a custom `destroy()` action to hide instances instead of deleting them, a custom action to list
    hidden instances, a custom action to revert the hidden field back to False.
    """

    def get_queryset(self):
        # # Filter out hidden instances by default
        # return self.queryset.filter(is_hidden=False)
        return super().get_queryset()

    def perform_destroy(self, instance):
        # Perform a soft delete
        instance.is_hidden = True
        instance.save()

    @action(detail=True, methods=['get', 'post'])
    def toggle_hidden(self, request, pk=None, *args, **kwargs):
        # Toggle the hidden status of an instance
        instance = self.get_object()
        instance.is_hidden = not instance.is_hidden
        instance.save()
        return Response({'status': f'Hidden status set to {instance.is_hidden}'}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False)
    def hidden(self, request, *args, **kwargs):
        # List all hidden instances
        hidden_instances = self.queryset.filter(is_hidden=True)
        page = self.paginate_queryset(hidden_instances)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(hidden_instances, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def active(self, request, *args, **kwargs):
        # List all active instances
        active_instances = self.queryset.filter(is_hidden=False)
        page = self.paginate_queryset(active_instances)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(active_instances, many=True)
        return Response(serializer.data)


class SearchDeleteViewSet(SoftDeleteWithModelViewSet):
    """
    A viewset that inherits from `SoftDeleteWithModelViewSet` and adds a custom `search` action to
    enable searching functionality.
    The search functionality can be accessed via the DRF API interface.
    """
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = []

    @action(detail=False)
    def search(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_hidden=False)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class PurchaseRequestViewSet(SearchDeleteViewSet):
    queryset = PurchaseRequest.objects.all()
    serializer_class = PurchaseRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['id', 'requester__username', 'suggested_vendor__name']

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)


class PurchaseRequestItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseRequestItem.objects.all()
    serializer_class = PurchaseRequestItemSerializer
    permission_classes = [permissions.IsAuthenticated]


class DepartmentViewSet(SoftDeleteWithModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]


class UnitOfMeasureViewSet(SearchDeleteViewSet):
    queryset = UnitOfMeasure.objects.all()
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['name',]


class VendorCategoryViewSet(SearchDeleteViewSet):
    queryset = VendorCategory.objects.all()
    serializer_class = VendorCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['name',]


class ProductCategoryViewSet(SearchDeleteViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['name',]


class VendorViewSet(SearchDeleteViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['company_name',]


class ProductViewSet(SearchDeleteViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['name', 'category__name', 'unit_of_measure__name', 'type', 'company__name',]


class RequestForQuotationViewSet(SearchDeleteViewSet):
    queryset = RequestForQuotation.objects.all()
    serializer_class = RequestForQuotationSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['vendor__company_name', 'status',]

    # for sending RFQs to vendor emails
    @action(detail=True, methods=['get', 'post'])
    def send_email(self, request, pk=None):
        rfq = self.get_object()
        try:
            rfq.send_email()
            return Response({'status': 'email sent'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RequestForQuotationItemViewSet(viewsets.ModelViewSet):
    queryset = RequestForQuotationItem.objects.all()
    serializer_class = RequestForQuotationItemSerializer
    permission_classes = [permissions.IsAuthenticated]


class RFQVendorQuoteViewSet(SearchDeleteViewSet):
    queryset = RFQVendorQuote.objects.all()
    serializer_class = RFQVendorQuoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['vendor__company_name',]


class RFQVendorQuoteItemViewSet(viewsets.ModelViewSet):
    queryset = RFQVendorQuoteItem.objects.all()
    serializer_class = RFQVendorQuoteItemSerializer
    permission_classes = [permissions.IsAuthenticated]


class PurchaseOrderViewSet(SearchDeleteViewSet):
    queryset = PurchaseOrder.objects.all()
    serializer_class = PurchaseOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['status', 'vendor__company_name']

    # for sending POs to vendor emails
    @action(detail=True, methods=['get', 'post'])
    def send_email(self, request, pk=None):
        po = self.get_object()
        try:
            po.send_email()
            return Response({'status': 'email sent'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PurchaseOrderItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrderItem.objects.all()
    serializer_class = PurchaseOrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]


class POVendorQuoteViewSet(SearchDeleteViewSet):
    queryset = POVendorQuote.objects.all()
    serializer_class = POVendorQuoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['vendor__company_name',]


class POVendorQuoteItemViewSet(viewsets.ModelViewSet):
    queryset = POVendorQuoteItem.objects.all()
    serializer_class = POVendorQuoteItemSerializer
    permission_classes = [permissions.IsAuthenticated]
