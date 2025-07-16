from django.urls import path, include
from rest_framework import routers
from . import views

router = routers.DefaultRouter()

router.register(r'currency', views.CurrencyViewSet, basename='currency')
router.register(r'vendors', views.VendorViewSet, basename='vendor')
router.register(r'unit-of-measure', views.UnitOfMeasureViewSet, basename='unit-of-measure')
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'purchase-request', views.PurchaseRequestViewSet, basename='purchase-request')
router.register(r'purchase-request-items', views.PurchaseRequestItemViewSet, basename='purchase-request-item')
router.register(r'request-for-quotation', views.RequestForQuotationViewSet, basename='request-for-quotation')
router.register(r'request-for-quotation-items', views.RequestForQuotationItemViewSet,
                basename='request-for-quotation-item')
router.register(r'purchase-order', views.PurchaseOrderViewSet, basename='purchase-order')
router.register(r'purchase-order-items', views.PurchaseOrderItemViewSet, basename='purchase-order-item')

urlpatterns = [
    path('', include(router.urls)),
]
