from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AccessGroupRightViewSet, NewTenantPasswordViewSet, NewTenantProfileViewSet, NewTenantUserViewSet, UserViewSet, PasswordChangeView, GroupViewSet, PermissionViewSet, GroupPermissionViewSet
from django.conf import settings
from django.conf.urls.static import static


router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'tenant-users', NewTenantUserViewSet, basename='tenant-user')
router.register(r'groups', GroupViewSet)
router.register(r'permissions', PermissionViewSet)
router.register(r'group-permissions', GroupPermissionViewSet, basename='group-permissions')
router.register(r'access-group-right', AccessGroupRightViewSet, basename='access-group-right')

urlpatterns = [
    path('', include(router.urls)),
    path('password-change/', PasswordChangeView.as_view(), name='password-change'),
    path('tenant-users/change-password', NewTenantPasswordViewSet.as_view({'post': 'change_password'}), name='change-password'),
    path('tenant-users/reset-password', NewTenantUserViewSet.as_view({'post': 'reset_password'}), name='reset-password'),
    path('tenant-users/edit/<int:id>/', NewTenantProfileViewSet.as_view({'patch': 'update_user_information'}), name='update-user-information'),
]

# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
                   path("ckeditor5/", include('django_ckeditor_5.urls')),
               ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
