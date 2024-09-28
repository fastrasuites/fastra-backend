from django.contrib import admin

from .models import Department, Product, Vendor, \
                    PurchaseRequest, PurchaseRequestItem, RequestForQuotation, \
                    RequestForQuotationItem

# Register your models here.

admin.site.register(PurchaseRequest)
admin.site.register(PurchaseRequestItem)


# admin.site.register(RequestForQuotation)
@admin.register(RequestForQuotation)
class RFQAdmin(admin.ModelAdmin):
    list_display = ('id', 'date_updated', 'expiry_date', 'vendor', 'status')


# admin.site.register(RequestForQuotationItem)
@admin.register(RequestForQuotationItem)
class RFQItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'request_for_quotation', 'product', 'qty', 'estimated_unit_price',
                    'get_total_price', )

    class Meta:
        model = RequestForQuotationItem
        order_by = ('request_for_quotation', '-id')


# admin.site.register(VendorCategory)
admin.site.register(Vendor)
admin.site.register(Product)
admin.site.register(Department)

