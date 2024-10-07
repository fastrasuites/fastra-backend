from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('api/admin/', admin.site.urls),
    path('api/accounting/', include('accounting.urls')),
    path('api/company', include('companies.urls')),
    path('api/hr/', include('hr.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/project-costing/', include('project_costing.urls')),
    path('api/purchase/', include('purchase.urls')),
    path('api/sales/', include('sales.urls')),
    path('api/users/', include('users.urls')),

    
]

urlpatterns += [
                   path("ckeditor5/", include('django_ckeditor_5.urls')),
               ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
