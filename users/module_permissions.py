from rest_framework.permissions import BasePermission
from .utils import user_has_permission
from rest_framework.permissions import BasePermission, SAFE_METHODS

class HasModulePermission(BasePermission):
    """
    This section checks if a user has the defined app/module/action permission.
    The view must define the attributes:
     `app_label`
     `model_name`
     `action_permission_map` (dict mapping DRF actions to your access rights, e.g. {"list": "view", "update": "edit"})
    """

    def has_permission(self, request, view):
        form_param = request.query_params.get("form")
        if form_param == "true" and request.method == "GET":
            return True

        app = getattr(view, "app_label", None)
        model = getattr(view, "model_name", None)
        permission_map = getattr(view, "action_permission_map", {})

        action = view.action  # like 'list', 'retrieve', 'create', etc.
        access_right = permission_map.get(action)

        if not all([app, model, access_right]):
            return False

        return user_has_permission(request.user, app, model, access_right)


class IsAdminOrIsSelf(BasePermission):
    """
    Custom permission to allow users to retrieve their own data,
    while only admins can access other users' data.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        if request.user.is_staff or request.user.is_superuser:
            return True

        return request.method in SAFE_METHODS and obj.user_id == request.user.id