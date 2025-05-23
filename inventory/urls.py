"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from rest_framework import routers

from .views import (DeliveryOrderReturnViewSet, DeliveryOrderViewSet, LocationViewSet, MultiLocationViewSet, StockAdjustmentViewSet, StockAdjustmentItemViewSet,
                    ScrapViewSet, ScrapItemViewSet)
from .views import (LocationViewSet, MultiLocationViewSet, StockAdjustmentViewSet, StockAdjustmentItemViewSet,
                    ScrapViewSet, ScrapItemViewSet, IncomingProductViewSet)

router = routers.DefaultRouter()

router.register(r'location', LocationViewSet, basename='location')
router.register(r'configuration/multi-location', MultiLocationViewSet, basename='multi-location')
router.register(r'stock-adjustment', StockAdjustmentViewSet, basename='stock-adjustment')
router.register(r'stock-adjustment/stock-adjustment-item', StockAdjustmentItemViewSet,
                basename='stock-adjustment-item')
router.register(r'scrap', ScrapViewSet, basename='scrap')
router.register(r'scrap/scrap-item', ScrapItemViewSet, basename='scrap-item')
# FOR THE DELIVERY ORDERS
router.register(r'delivery-orders', DeliveryOrderViewSet, basename='delivery-orders')

router.register(r'delivery-order-returns', DeliveryOrderReturnViewSet, basename='delivery-order-returns')

router.register(r'incoming-product', IncomingProductViewSet, basename='incoming-product')
# router.register(r'incoming-product/incoming-product-item', IncomingProductItemViewSet,
# basename='incoming-product-item')

urlpatterns = [
    path('', include(router.urls)),
    # START FOR THE DELIVERY ORDERS
    path('delivery-order/check-availability/<int:pk>/', DeliveryOrderViewSet.as_view({'get': 'check_availability'})),
    path('delivery-order/confirm-delivery/<int:pk>/', DeliveryOrderViewSet.as_view({'get': 'confirm_delivery'})),
    # END FOR THE DELIVERY ORDERS

    # START FOR THE RETURN RECORDS
    # END FOR THE RETURN RECORDS
]
