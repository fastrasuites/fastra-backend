from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('registration.urls'), name='registration'),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

]

urlpatterns += [
                   path("ckeditor5/", include('django_ckeditor_5.urls')),
               ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
