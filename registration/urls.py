from django.urls import path
from .views import TenantRegistrationViewSet

urlpatterns = [
    path('register/', TenantRegistrationViewSet.as_view({'post': 'create'}), name='register'),
]
