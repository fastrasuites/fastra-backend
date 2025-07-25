from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChangeAdminPassword, MarkOnboardedView, OnboardingStatusView, TenantViewSet, VerifyEmail, RequestForgottenPasswordView,\
    ResendVerificationEmail, UpdateCompanyProfileView, ResendOTPView, ProtectedView

from rest_framework_simplejwt.views import (

    TokenRefreshView,
)

# router = DefaultRouter()
# router.register('tenants', TenantViewSet, basename='tenant')


urlpatterns = [
    # path('', include(router.urls)),
    path('email-verify', VerifyEmail.as_view(), name='email-verify'),
    path('resend-verification-email/', ResendVerificationEmail.as_view(), name='resend-verification-email'),

    path('request-forgotten-password/', RequestForgottenPasswordView.as_view(), name='request-password-reset'),
    #path('reset-password/', ForgottenPasswordView.as_view(), name='reset-password'),
    #path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),

    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('update-company-profile/', UpdateCompanyProfileView.as_view(), name='update-company-profile'),
    path('change-admin-password/', ChangeAdminPassword.as_view(), name='change-admin-password'),
    path('onboarding-status/', OnboardingStatusView.as_view(), name='onboarding_status'),
    path('mark-onboarded/', MarkOnboardedView.as_view(), name='mark_onboarded'),

    path('test/', ProtectedView.as_view())

]
