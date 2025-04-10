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

from .views import (LocationViewSet, MultiLocationViewSet, StockAdjustmentViewSet, StockAdjustmentItemViewSet,
                    ScrapViewSet, ScrapItemViewSet)

router = routers.DefaultRouter()

router.register(r'location', LocationViewSet, basename='location')
router.register(r'configuration/multi-location', MultiLocationViewSet, basename='multi-location')
router.register(r'stock-adjustment', StockAdjustmentViewSet, basename='stock-adjustment')
router.register(r'stock-adjustment/stock-adjustment-item', StockAdjustmentItemViewSet,
                basename='stock-adjustment-item')
router.register(r'scrap', ScrapViewSet, basename='scrap')
router.register(r'scrap/scrap-item', ScrapItemViewSet, basename='scrap-item')

urlpatterns = [
    path('', include(router.urls)),
]
