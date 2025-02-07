from django.urls import path

from .views import TenantRegistrationViewSet, LoginView


urlpatterns = [
    path('register/', TenantRegistrationViewSet.as_view({'post': 'create'}), name='register'),
    path('login/', LoginView.as_view(), name='login'),
]
