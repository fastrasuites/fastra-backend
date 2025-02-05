from django.urls import path

from companies.views import LoginView
from .views import TenantRegistrationViewSet

urlpatterns = [
    path('register/', TenantRegistrationViewSet.as_view({'post': 'create'}), name='register'),
    path('login/', LoginView.as_view(), name='login'),
]
