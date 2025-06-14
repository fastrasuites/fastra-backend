from django.urls import path
from .views import NewGroupViewSet
from .views import TenantRegistrationViewSet, LoginView


urlpatterns = [
    path('register/', TenantRegistrationViewSet.as_view({'post': 'create'}), name='register'),
    path('login/', LoginView.as_view(), name='login'),

    path('new-groups/', NewGroupViewSet.as_view({'post': 'create', 'get': 'list'}), name='new-groups'),
]
