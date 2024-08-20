from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantRegistrationViewSet, TenantViewSet, \
VerifyEmail, LoginView, RequestPasswordResetView, \
ResetPasswordView, ResendVerificationEmail, UpdateCompanyProfileView

from rest_framework_simplejwt.views import (

    TokenRefreshView,
)

router = DefaultRouter()
router.register('tenants', TenantViewSet, basename='tenant')

urlpatterns = [
    path('register/', TenantRegistrationViewSet.as_view({'post': 'create'}), name='register'),
    path('', include(router.urls)),
    path('email-verify/', VerifyEmail.as_view(), name='email-verify'),
    path('login/', LoginView.as_view(), name='login'),
    path('request-password-reset/', RequestPasswordResetView.as_view(), name='request-password-reset'),
    path('reset-password/<str:uidb64>/<str:token>/', ResetPasswordView.as_view(), name='reset-password'),
    path('resend-verification-email/<str:token>/', ResendVerificationEmail.as_view(), name='resend-verification-email'),

    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('update-company-profile/', UpdateCompanyProfileView.as_view(), name='update-company-profile'),


]