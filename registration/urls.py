from django.urls import path
from companies.views import RequestForgottenPasswordView, ResetPasswordView, ResendOTPView,VerifyOTPView
from .views import TenantRegistrationViewSet, LoginView


urlpatterns = [
    path('register/', TenantRegistrationViewSet.as_view({'post': 'create'}), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('request-forgotten-password/', RequestForgottenPasswordView.as_view(), name='request-password-reset'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
]

#path('reset-password/', ForgottenPasswordView.as_view(), name='reset-password'),
