from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantUserViewSet, PasswordChangeView, GroupViewSet, PermissionViewSet, GroupPermissionViewSet
from django.conf import settings
from django.conf.urls.static import static


router = DefaultRouter()
router.register(r'tenant-users', TenantUserViewSet, basename='tenant-user')
router.register(r'groups', GroupViewSet)
router.register(r'permissions', PermissionViewSet)
router.register(r'group-permissions', GroupPermissionViewSet, basename='group-permissions')

urlpatterns = [
    path('', include(router.urls)),
    path('password-change/', PasswordChangeView.as_view(), name='password-change')
]

# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
                   path("ckeditor5/", include('django_ckeditor_5.urls')),
               ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
