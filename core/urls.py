from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounting/', include('accounting.urls')),
    path('companies/', include('companies.urls')),
    path('hr/', include('hr.urls')),
    path('inventory/', include('inventory.urls')),
    path('project-costing/', include('project_costing.urls')),
    path('purchase/', include('purchase.urls')),
    path('sales/', include('sales.urls')),
    
    # path('users/', include('users.urls')),

    
]

urlpatterns += [
                   path("ckeditor5/", include('django_ckeditor_5.urls')),
               ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
