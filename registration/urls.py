from django.urls import path
from .views import AccessRightViewSet, ApplicationViewSet
from companies.views import RequestForgottenPasswordView, ForgottenPasswordView, ResendOTPView
from .views import TenantRegistrationViewSet, LoginView
from rest_framework import routers

router = routers.DefaultRouter()

router.register(r'application', ApplicationViewSet, basename='application')
# router.register(r'application-module', ApplicationModuleViewSet, basename='application-module')
router.register(r'access-right', AccessRightViewSet, basename='access-right')


urlpatterns = [
    path('register/', TenantRegistrationViewSet.as_view({'post': 'create'}), name='register'),
    path('login/', LoginView.as_view(), name='login'),

    # path('new-groups/', NewGroupViewSet.as_view({'post': 'create', 'get': 'list'}), name='new-groups'),
    # path('new-groups/<int:pk>/', NewGroupViewSet.as_view({'patch': 'partial_update'}), name='new-groups-edit'),
    path('request-forgotten-password/', RequestForgottenPasswordView.as_view(), name='request-password-reset'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
]

urlpatterns += router.urls
