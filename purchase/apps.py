from django.apps import AppConfig
from django.conf import settings
import os

class PurchaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'purchase'

    def ready(self):
        media_root = settings.MEDIA_ROOT
        if not os.path.exists(media_root):
            os.makedirs(media_root, exist_ok=True)
        
        vendor_profiles_dir = os.path.join(media_root, 'vendor_profiles')
        if not os.path.exists(vendor_profiles_dir):
            os.makedirs(vendor_profiles_dir, exist_ok=True)
