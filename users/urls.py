from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantUserViewSet, PasswordChangeView, TenantPermissionViewSet, UserPermissionViewSet
from django.conf import settings
from django.conf.urls.static import static


router = DefaultRouter()
router.register(r'tenant-users', TenantUserViewSet, basename='tenant-user')
router.register(r'tenant-permissions', TenantPermissionViewSet, basename='tenant-permission')
router.register(r'user-permissions', UserPermissionViewSet, basename='user-permission')

urlpatterns = [
    path('', include(router.urls)),
    path('password-change/', PasswordChangeView.as_view(), name='password-change')
]

# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
                   path("ckeditor5/", include('django_ckeditor_5.urls')),
               ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
