import json
import requests
import os

from openpyxl import load_workbook
from urllib.parse import quote

from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.exceptions import ObjectDoesNotExist

from django_filters.rest_framework import DjangoFilterBackend
from django_tenants.utils import tenant_context
from rest_framework import viewsets, status, mixins, filters, permissions, serializers
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import action, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from companies.permissions import HasTenantAccess
from core.utils import enforce_tenant_schema
from users.models import TenantUser
from .models import PurchaseRequest, PurchaseRequestItem, Department, Vendor, Product, RequestForQuotation, \
    RequestForQuotationItem, UnitOfMeasure, RFQVendorQuote, RFQVendorQuoteItem, \
    PurchaseOrder, PurchaseOrderItem, POVendorQuote, POVendorQuoteItem, PRODUCT_CATEGORY, Currency
from .serializers import PurchaseRequestSerializer, DepartmentSerializer, VendorSerializer, \
    ProductSerializer, RequestForQuotationSerializer, RequestForQuotationItemSerializer, \
    UnitOfMeasureSerializer, \
    PurchaseRequestItemSerializer, RFQVendorQuoteSerializer, RFQVendorQuoteItemSerializer, \
    PurchaseOrderSerializer, PurchaseOrderItemSerializer, POVendorQuoteSerializer, \
    POVendorQuoteItemSerializer, ExcelUploadSerializer, CurrencySerializer
from .utils import generate_model_pdf


class SoftDeleteWithModelViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.CreateModelMixin,
                                 mixins.RetrieveModelMixin, mixins.UpdateModelMixin):
    """
    A viewset that provides default `list()`, `create()`, `retrieve()`, `update()`, `partial_update()`,
    and a custom `destroy()` action to hide instances instead of deleting them, a custom action to list
    hidden instances, a custom action to revert the hidden field back to False.
    """

    def get_queryset(self):
        # # Filter out hidden instances by default
        # return self.queryset.filter(is_hidden=False)
        return super().get_queryset()

    @action(detail=True, methods=['put', 'patch'])
    def toggle_hidden_status(self, request, pk=None, *args, **kwargs):
        # Toggle the hidden status of an instance
        instance = self.get_object()
        instance.is_hidden = not instance.is_hidden
        instance.save()
        return Response({'status': f'Hidden status set to {instance.is_hidden}'}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['delete'])
    def soft_delete(self, request, pk=None, *args, **kwargs):
        # Soft delete an instance
        instance = self.get_object()
        instance.is_hidden = True
        instance.save()
        return Response({'status': 'hidden'}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def hidden_list(self, request, *args, **kwargs):
        # List all hidden instances
        hidden_instances = self.queryset.filter(is_hidden=True)
        page = self.paginate_queryset(hidden_instances)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(hidden_instances, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def active_list(self, request, *args, **kwargs):
        # List all active instances
        active_instances = self.queryset.filter(is_hidden=False)
        page = self.paginate_queryset(active_instances)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(active_instances, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SearchDeleteViewSet(SoftDeleteWithModelViewSet):
    """
    A viewset that inherits from `SoftDeleteWithModelViewSet` and adds a custom `search` action to
    enable searching functionality.
    The search functionality can be accessed via the DRF API interface.
    """
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = []

    @action(detail=False, methods=['get'])
    def search(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset()).filter(is_hidden=False)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PurchaseRequestViewSet(SearchDeleteViewSet):
    queryset = PurchaseRequest.objects.all()
    serializer_class = PurchaseRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['id', 'requester__username', 'suggested_vendor__name']

    def perform_create(self, serializer):
        # # Ensure the user is a TenantUser
        # user = self.request.user
        # # Ensure we are operating within the correct tenant schema
        # tenant = self.request.tenant  # Get the current tenant
        #
        # with tenant_context(tenant):  # Switch to the tenant's schema
        #     try:
        #         tenant_user = TenantUser.objects.get(user_id=user.id)
        #     except ObjectDoesNotExist:
        #         raise serializers.ValidationError("Requester must be a TenantUser within the tenant schema.")

        serializer.save()

    @action(detail=False, methods=['get'])
    def draft_list(self, request):
        queryset = PurchaseRequest.pr_draft.all()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending_list(self, request):
        queryset = PurchaseRequest.pr_pending.all()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def approved_list(self, request):
        queryset = PurchaseRequest.pr_approved.all()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def rejected_list(self, request):
        queryset = PurchaseRequest.pr_rejected.all()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['put', 'patch'])
    def submit(self, request, pk=None):
        purchase_request = self.get_object()
        purchase_request.submit()
        return Response({'status': 'submitted'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['put', 'patch'])
    def approve(self, request, pk=None):
        purchase_request = self.get_object()
        if request.user.has_perm('approve_purchase_request'):
            purchase_request.approve()
            return Response({'status': 'approved'}, status=status.HTTP_200_OK)
        return Response({'status': 'permission denied'}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['put', 'patch'])
    def reject(self, request, pk=None):
        purchase_request = self.get_object()
        if request.user.has_perm('reject_purchase_request'):
            purchase_request.reject()
            return Response({'status': 'rejected'}, status=status.HTTP_200_OK)
        return Response({'status': 'permission denied'}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['post'])
    def convert_to_rfq(self, request, pk=None):
        try:
            # Get the approved purchase request
            purchase_request = self.get_object()

            if purchase_request.status != 'approved':
                return Response({"detail": "Only approved purchase requests can be converted to RFQs."},
                                status=status.HTTP_400_BAD_REQUEST)

            # Create the RFQ
            rfq = RequestForQuotation.objects.create(
                purchase_request=purchase_request,
                vendor=purchase_request.vendor,  # Assuming vendor is used
                expiry_date=None,  # Can be set dynamically or left blank
                currency=purchase_request.currency,  # Can be set dynamically or left blank
                status='draft',
                date_created=timezone.now(),
                date_updated=timezone.now(),
                is_hidden=False,
            )

            # Create RFQ items from the PurchaseRequest items
            for pr_item in purchase_request.items.all():
                RequestForQuotationItem.objects.create(
                    request_for_quotation=rfq,
                    product=pr_item.product,
                    description=pr_item.description,
                    unit_of_measure=pr_item.unit_of_measure,
                    qty=pr_item.qty,
                    estimated_unit_price=pr_item.estimated_unit_price,
                )

            return Response({
                "detail": "RFQ created successfully",
                "rfq_id": rfq.id
            }, status=status.HTTP_201_CREATED)

        except PurchaseRequest.DoesNotExist:
            return Response({"detail": "Purchase request not found."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"detail": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


class PurchaseRequestItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseRequestItem.objects.all()
    serializer_class = PurchaseRequestItemSerializer
    permission_classes = [permissions.IsAuthenticated]


class DepartmentViewSet(SearchDeleteViewSet):
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated, HasTenantAccess]
    queryset = Department.objects.all()

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class CurrencyViewSet(SearchDeleteViewSet):
    serializer_class = CurrencySerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Currency.objects.all()


class UnitOfMeasureViewSet(SearchDeleteViewSet):
    queryset = UnitOfMeasure.objects.all()
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['unit_name', 'unit_category']


# class VendorCategoryViewSet(SearchDeleteViewSet):
#     queryset = VendorCategory.objects.all()
#     serializer_class = VendorCategorySerializer
#     permission_classes = [permissions.IsAuthenticated]
#     search_fields = ['name',]


class VendorViewSet(SearchDeleteViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    search_fields = ['company_name', 'email']

    def create(self, request, *args, **kwargs):
        serializer = VendorSerializer(data=request.data)
        if serializer.is_valid():
            vendor = serializer.save()
            return Response({
                "message": "Vendor created successfully",
                "vendor": {
                    "url": vendor.url,
                    "company_name": vendor.company_name,
                    "email": vendor.email,
                    "address": vendor.address,
                    "profile_picture": request.build_absolute_uri(
                        vendor.profile_picture.url) if vendor.profile_picture else None,
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = VendorSerializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            vendor = serializer.save()
            return Response({
                "message": "Vendor updated successfully",
                "vendor": {
                    "url": vendor.url,
                    "company_name": vendor.company_name,
                    "email": vendor.email,
                    "address": vendor.address,
                    "profile_picture": request.build_absolute_uri(
                        vendor.profile_picture.url) if vendor.profile_picture else None,
                }
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
                    company_name, email, address, phone_number = row[:4]

                    try:
                        vendor = Vendor(
                            company_name=company_name,
                            email=email,
                            address=address,
                            phone_number=phone_number,
                            # is_hidden=bool(is_hidden)
                        )
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
    search_fields = ['product_name', 'product_category', 'unit_of_measure__name', ]

    @action(detail=False, methods=['POST'], serializer_class=ExcelUploadSerializer)
    def upload_excel(self, request):
        serializer = ExcelUploadSerializer(data=request.data)
        if serializer.is_valid():
            excel_file = serializer.validated_data['file']
            check_for_duplicates = serializer.validated_data.get('check_for_duplicates', False)

            if not isinstance(excel_file, InMemoryUploadedFile):
                return Response({"error": "Invalid file format"}, status=400)

            try:
                workbook = load_workbook(excel_file)
                sheet = workbook.active

                products_count = sheet.max_row - 1
                products_created = 0
                products_updated = 0
                errors = []

                valid_product_categories = [choice[0] for choice in PRODUCT_CATEGORY]

                for row in sheet.iter_rows(min_row=2, values_only=True):
                    (product_name, product_description, product_category, unit_of_measure,
                     available_product_quantity, total_quantity_purchased) = row[:6]

                    print(f"{products_count - (products_created + products_updated)} products remaining")

                    product_category = slugify(product_category)

                    # Check if the product_category is among the options available
                    if product_category not in valid_product_categories:
                        return Response({
                            "errors": f"Invalid category '{product_category}' for {product_name}. "
                                      f"Valid categories are: {', '.join(valid_product_categories)}. "
                                      f"Created {products_created}, Updated {products_updated}."
                        }, status=400)

                    unit_of_measure_name = row[3]

                    # Fetch the UnitOfMeasure instance, or create it if it doesn't exist
                    unit_of_measure, created = UnitOfMeasure.objects.get_or_create(name=unit_of_measure_name)

                    try:
                        # Check if the product already exists by product_name
                        existing_product = Product.objects.filter(product_name__iexact=product_name,
                                                                  product_category__iexact=product_category).first()

                        if check_for_duplicates and existing_product:
                            # Update the existing product quantities
                            existing_product.product_description = product_description
                            existing_product.unit_of_measure = unit_of_measure
                            existing_product.available_product_quantity += available_product_quantity
                            existing_product.total_quantity_purchased += total_quantity_purchased
                            existing_product.save()
                            products_updated += 1
                        else:
                            # Create a new product if no duplicates are found or check_for_duplicates is False
                            product = Product(
                                product_name=product_name,
                                product_description=product_description,
                                product_category=product_category,
                                unit_of_measure=unit_of_measure,
                                available_product_quantity=available_product_quantity,
                                total_quantity_purchased=total_quantity_purchased,
                            )
                            product.save()
                            products_created += 1

                    except Exception as e:
                        errors.append(f"Error processing product {product_name}: {str(e)}")

                return Response({
                    "message": f"Successfully created {products_created} products, updated {products_updated} products",
                    "errors": errors
                }, status=201)

            except Exception as e:
                return Response({"error": f"Error processing Excel file: {str(e)}"}, status=400)
        else:
            return Response(serializer.errors, status=400)

    @action(detail=False, methods=['DELETE', 'GET'], permission_classes=[IsAdminUser], url_path='delete-all',
            url_name='delete_all_products')
    def delete_all_products(self, request):
        deleted_count, _ = Product.objects.all().delete()

        return Response(
            {"message": f"Successfully deleted {deleted_count} products."},
            status=status.HTTP_200_OK
        )


class RequestForQuotationViewSet(SearchDeleteViewSet):
    queryset = RequestForQuotation.objects.all()
    serializer_class = RequestForQuotationSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['vendor__company_name', 'status', 'purchase_request__id']

    @action(detail=True, methods=['get'])
    def check_rfq_editable(self, rfq):
        """Check if the RFQ is editable (not submitted or rejected)."""
        if rfq.is_submitted:
            return False, 'This RFQ has already been submitted and cannot be edited.'
        return True, ''

    @action(detail=True, methods=['get'])
    def check_rfq_mailable(self, rfq):
        """Check if the RFQ meets the criteria to be sent to vendors (not draft or rejected)."""
        if rfq.status in ['rejected', 'draft']:
            return False, 'This RFQ cannot be sent as it has been rejected or not submitted.'
        if rfq.is_expired:
            return False, 'This RFQ has expired and cannot be sent.'
        return True, ''

    # for sending RFQs to vendor emails
    @action(detail=True, methods=['post'])
    def send_email(self, request, pk=None):
        rfq = self.get_object()

        # Check if the RFQ has expired
        if rfq.is_expired:
            return Response({'error': 'Cannot send expired RFQ.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Generate the PDF
            pdf_response = generate_model_pdf(rfq)
            if not pdf_response:
                return Response({'error': 'Error generating PDF.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            pdf_content = pdf_response.content

            # Create and send the email
            subject = f"Request for Quotation: {rfq.id}"
            body = (f"Please find attached the RFQ {rfq.id}. The deadline"
                    f" for response is {rfq.expiry_date.strftime('%Y-%m-%d') if rfq.expiry_date else 'None'}.")
            # email = EmailMessage(subject, body, settings.EMAIL_HOST_USER, [rfq.vendor.email])
            # email.attach(f"RFQ_{rfq.id}.pdf", pdf_content, 'application/pdf')

            mailto_link = f'mailto:{rfq.vendor.email}?subject={quote(subject)}&body={quote(body)}'

            # Prepare the response
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="RFQ_{rfq.id}.pdf"'

            # Embed the mailto link in the response headers for the front-end to use
            response['X-Mailto-Link'] = mailto_link

            return response

            # email.send()

            # return Response({'status': 'email sent'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['put', 'patch'])
    def submit(self, request, pk=None):
        rfq = self.get_object()
        editable, message = self.check_rfq_editable(rfq)

        if not editable:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

        rfq.submit()
        return Response({'status': 'pending'})

    @action(detail=True, methods=['put', 'patch'])
    def approve(self, request, pk=None):
        rfq = self.get_object()
        if request.user.has_perm('approve_request_for_quotation'):
            rfq.approve()
            return Response({'status': 'approved'})
        return Response({'status': 'permission denied'}, status=403)

    @action(detail=True, methods=['put', 'patch'])
    def reject(self, request, pk=None):
        rfq = self.get_object()
        if request.user.has_perm('reject_request_for_quotation'):
            rfq.reject()
            return Response({'status': 'rejected'})
        return Response({'status': 'permission denied'}, status=403)

    def get_queryset(self):
        queryset = super().get_queryset()  # Use the superclass queryset
        rfq_status = self.request.query_params.get('status')
        expired = self.request.query_params.get('expired')

        # Filter by status if provided
        if rfq_status:
            queryset = queryset.filter(status=rfq_status)

        # Filter by expiration status if provided
        if expired is not None:
            queryset = queryset.filter(expiry_date__lt=timezone.now()) if expired == 'true' else queryset.filter(
                expiry_date__gte=timezone.now())

        return queryset

    @action(detail=True, methods=['post'])
    def convert_to_po(self, request, pk=None):
        try:
            # Get the approved purchase request
            rfq = self.get_object()

            if rfq.status != 'approved':
                return Response({"detail": "Only approved Requests For Quotation can be converted to Purchase Orders."},
                                status=status.HTTP_400_BAD_REQUEST)
            if not rfq.actual_price:
                return Response({'error': 'Actual price is required to convert to PO.'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Create the Purchase Order
            po = PurchaseOrder.objects.create(
                vendor=rfq.vendor,
                status='draft',
                created_by=request.user,
                currency=rfq.currency,
                date_created=timezone.now(),
                date_updated=timezone.now(),
                is_hidden=False,
            )

            # Create po items from the RFQ items
            for rfq_item in rfq.items.all():
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    product=rfq_item.product,
                    description=rfq_item.description,
                    qty=rfq_item.qty,
                    unit_of_measure=rfq_item.unit_of_measure,
                    estimated_unit_price=rfq_item.estimated_unit_price,
                )

            return Response({
                "detail": "Purchase Order created successfully",
                "po_id": po.id
            }, status=status.HTTP_201_CREATED)

        except RequestForQuotation.DoesNotExist:
            return Response({"detail": "Request For Quotation not found."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"detail": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


class RequestForQuotationItemViewSet(viewsets.ModelViewSet):
    queryset = RequestForQuotationItem.objects.all()
    serializer_class = RequestForQuotationItemSerializer
    permission_classes = [permissions.IsAuthenticated]


class RFQVendorQuoteViewSet(SearchDeleteViewSet):
    queryset = RFQVendorQuote.objects.all()
    serializer_class = RFQVendorQuoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['vendor__company_name', ]


class RFQVendorQuoteItemViewSet(viewsets.ModelViewSet):
    queryset = RFQVendorQuoteItem.objects.all()
    serializer_class = RFQVendorQuoteItemSerializer
    permission_classes = [permissions.IsAuthenticated]


class PurchaseOrderViewSet(SearchDeleteViewSet):
    queryset = PurchaseOrder.objects.all()
    serializer_class = PurchaseOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['status', 'vendor__company_name']

    @action(detail=True, methods=['get'])
    def check_po_editable(self, po):
        """Check if the PO is editable (not submitted or rejected)."""
        if po.is_submitted:
            return False, 'This purchase order has already been submitted and cannot be edited.'
        return True, ''

    @action(detail=True, methods=['get'])
    def check_po_mailable(self, po):
        """Check if the PO meets the criteria to be sent to vendors (not draft or rejected)."""
        if po.status in ['rejected', 'draft']:
            return False, 'This purchase order cannot be sent as it has been rejected or not submitted.'
        if po.is_expired:
            return False, 'This purchase order has expired and cannot be sent.'
        return True, ''

    # for sending POs to vendor emails
    @action(detail=True, methods=['post'])
    def send_email(self, request, pk=None):
        po = self.get_object()

        try:
            # Generate the PDF
            pdf_response = generate_model_pdf(po)
            if not pdf_response:
                return Response({'error': 'Error generating PDF.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            pdf_content = pdf_response.content

            # Create and send the email
            subject = f"Purchase Order: {po.id}"
            body = f"Please find attached the RFQ {po.id}."
            # email = EmailMessage(subject, body, settings.EMAIL_HOST_USER, [po.vendor.email])
            # email.attach(f"PO_{po.id}.pdf", pdf_content, 'application/pdf')

            mailto_link = f'mailto:{po.vendor.email}?subject={quote(subject)}&body={quote(body)}'

            # Prepare the response
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="PO_{po.id}.pdf"'

            # Embed the mailto link in the response headers for the front-end to use
            response['X-Mailto-Link'] = mailto_link

            return response

            # email.send()

            # return Response({'status': 'email sent'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PurchaseOrderItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrderItem.objects.all()
    serializer_class = PurchaseOrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    @enforce_tenant_schema
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class POVendorQuoteViewSet(SearchDeleteViewSet):
    queryset = POVendorQuote.objects.all()
    serializer_class = POVendorQuoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['vendor__company_name', ]

    @enforce_tenant_schema
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class POVendorQuoteItemViewSet(viewsets.ModelViewSet):
    queryset = POVendorQuoteItem.objects.all()
    serializer_class = POVendorQuoteItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    @enforce_tenant_schema
    def get(self, request, *args, **kwargs):
        # Custom logic can be added here
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
