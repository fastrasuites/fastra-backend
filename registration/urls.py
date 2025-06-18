from django.urls import path
from .views import NewGroupViewSet
from companies.views import RequestForgottenPasswordView, ForgottenPasswordView, ResendOTPView
from .views import TenantRegistrationViewSet, LoginView


urlpatterns = [
    path('register/', TenantRegistrationViewSet.as_view({'post': 'create'}), name='register'),
    path('login/', LoginView.as_view(), name='login'),

    path('new-groups/', NewGroupViewSet.as_view({'post': 'create', 'get': 'list'}), name='new-groups'),
    path('request-forgotten-password/', RequestForgottenPasswordView.as_view(), name='request-password-reset'),
    path('reset-password/', ForgottenPasswordView.as_view(), name='reset-password'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
]
