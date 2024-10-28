# from .views import TenantRegistrationViewSet
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantCreationViewSet, OTPVerificationViewSet, TenantFinalizationViewSet, TenantAccessViewSet

router = DefaultRouter()
router.register(r'tenant-creation', TenantCreationViewSet, basename='tenant-creation')
router.register(r'otp-verification', OTPVerificationViewSet, basename='otp-verification')
router.register(r'tenant-finalization', TenantFinalizationViewSet, basename='tenant-finalization')
router.register(r'tenant-access', TenantAccessViewSet, basename='tenant-access')

urlpatterns = [
    path('', include(router.urls)),
]