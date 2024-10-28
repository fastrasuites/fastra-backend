from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static

# from .views import UserViewSet, TenantUserViewSet, PasswordChangeView, GroupViewSet,
# PermissionViewSet, GroupPermissionViewSet
from .views import LoginViewSet, RegisterViewSet, LogoutViewSet, UserDetailsViewSet, ForgotPasswordViewSet, \
    ResetPasswordViewSet


router = DefaultRouter()
router.register(r'login', LoginViewSet, basename='login')
router.register(r'register', RegisterViewSet, basename='register')
router.register(r'logout', LogoutViewSet, basename='logout')
router.register(r'user', UserDetailsViewSet, basename='user')
router.register(r'forgot-password', ForgotPasswordViewSet, basename='forgot-password')
router.register(r'reset-password', ResetPasswordViewSet, basename='reset-password')
# router.register(r'users', UserViewSet, basename='user')
# router.register(r'tenant-users', TenantUserViewSet, basename='tenant-user')
# router.register(r'groups', GroupViewSet)
# router.register(r'permissions', PermissionViewSet)
# router.register(r'group-permissions', GroupPermissionViewSet, basename='group-permissions')

urlpatterns = [
    path('', include(router.urls)),
    # path('password-change/', PasswordChangeView.as_view(), name='password-change')
]

# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
                   path("ckeditor5/", include('django_ckeditor_5.urls')),
               ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
