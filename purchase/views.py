from django.shortcuts import render
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, generics, filters
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import PurchaseRequest, PurchaseRequestItem, Department, Vendor, Product, RequestForQuotation, \
    RequestForQuotationItem, ProductCategory, UnitOfMeasure, RFQVendorQuote, RFQVendorQuoteItem, \
    PurchaseOrder, PurchaseOrderItem, POVendorQuote, POVendorQuoteItem
from .serializers import PurchaseRequestSerializer, DepartmentSerializer, VendorSerializer, \
    ProductSerializer, RequestForQuotationSerializer, RequestForQuotationItemSerializer, \
     ProductCategorySerializer, UnitOfMeasureSerializer, \
    PurchaseRequestItemSerializer, RFQVendorQuoteSerializer, RFQVendorQuoteItemSerializer, \
    PurchaseOrderSerializer, PurchaseOrderItemSerializer, POVendorQuoteSerializer, \
    POVendorQuoteItemSerializer, ExcelUploadSerializer
from django.core.files.uploadedfile import InMemoryUploadedFile
from openpyxl import load_workbook
import requests
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import os

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

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        purchase_request = self.get_object()
        purchase_request.submit()
        return Response({'status': 'submitted'})

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        purchase_request = self.get_object()
        if request.user.has_perm('approve_purchase_request'):
            purchase_request.approve()
            return Response({'status': 'approved'})
        return Response({'status': 'permission denied'}, status=403)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        purchase_request = self.get_object()
        if request.user.has_perm('reject_purchase_request'):
            purchase_request.reject()
            return Response({'status': 'rejected'})
        return Response({'status': 'permission denied'}, status=403)



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


# class VendorCategoryViewSet(SearchDeleteViewSet):
#     queryset = VendorCategory.objects.all()
#     serializer_class = VendorCategorySerializer
#     permission_classes = [permissions.IsAuthenticated]
#     search_fields = ['name',]


class ProductCategoryViewSet(SearchDeleteViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['name',]



class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['company_name', 'email']

    @action(detail=False, methods=['POST'], serializer_class=ExcelUploadSerializer)
    def upload_excel(self, request):
        serializer = ExcelUploadSerializer(data=request.data)
        if serializer.is_valid():
            excel_file = serializer.validated_data['file']
            if not isinstance(excel_file, InMemoryUploadedFile):
                return Response({"error": "Invalid file format"}, status=400)

            try:
                workbook = load_workbook(excel_file)
                sheet = workbook.active

                vendors_created = 0
                errors = []

                for row in sheet.iter_rows(min_row=2, values_only=True):
                    company_name, email, address, phone_number, profile_picture_url = row[:5]
                    
                    try:
                        vendor = Vendor(
                            company_name=company_name,
                            email=email,
                            address=address,
                            phone_number=phone_number,
                            # is_hidden=bool(is_hidden)
                        )

                        if profile_picture_url:
                            try:
                                response = requests.get(profile_picture_url)
                                if response.status_code == 200:
                                    # Generate a unique filename
                                    file_name = f"{company_name.replace(' ', '_')}_profile.jpg"
                                    file_path = os.path.join('vendor_profiles', file_name)
                                    
                                    # Save the image using default_storage
                                    file_name = default_storage.save(file_path, ContentFile(response.content))
                                    
                                    # Set the profile_picture field to the saved file path
                                    vendor.profile_picture = file_name
                            except Exception as e:
                                errors.append(f"Error downloading profile picture for {company_name}: {str(e)}")

                        vendor.save()
                        vendors_created += 1
                    except Exception as e:
                        errors.append(f"Error creating vendor {company_name}: {str(e)}")

                return Response({
                    "message": f"Successfully created {vendors_created} vendors",
                    "errors": errors
                }, status=201)

            except Exception as e:
                return Response({"error": f"Error processing Excel file: {str(e)}"}, status=400)
        else:
            return Response(serializer.errors, status=400)

    @action(detail=True, methods=['POST'])
    def upload_profile_picture(self, request, pk=None):
        vendor = self.get_object()
        if 'profile_picture' not in request.FILES:
            return Response({"error": "No file provided"}, status=400)
        
        vendor.profile_picture = request.FILES['profile_picture']
        vendor.save()
        return Response({"message": "Profile picture uploaded successfully"}, status=200)

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
