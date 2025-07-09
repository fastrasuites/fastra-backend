from rest_framework.permissions import BasePermission
from .utils import user_has_permission

class HasModulePermission(BasePermission):
    """
    This section checks if a user has the defined app/module/action permission.
    The view must define the attributes:
     `app_label`
     `model_name`
     `action_permission_map` (dict mapping DRF actions to your access rights, e.g. {"list": "view", "update": "edit"})
    """

    def has_permission(self, request, view):
        app = getattr(view, "app_label", None)
        model = getattr(view, "model_name", None)
        permission_map = getattr(view, "action_permission_map", {})

        action = view.action  # like 'list', 'retrieve', 'create', etc.
        access_right = permission_map.get(action)

        if not all([app, model, access_right]):
            return False

        return user_has_permission(request.user, app, model, access_right)
