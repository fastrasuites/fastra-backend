from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model

User = get_user_model()

@receiver(m2m_changed, sender=Group.permissions.through)
def sync_group_permissions(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        users = instance.user_set.all()
        for user in users:
            # Get all permissions from all of the user's groups
            group_permissions = Permission.objects.filter(group__user=user).distinct()
            
            # Add these permissions directly to the user's permissions
            for permission in group_permissions:
                user.user_permissions.add(permission)

            # Remove any permissions that are no longer in any of the user's groups
            user_permissions = user.user_permissions.all()
            for permission in user_permissions:
                if permission not in group_permissions:
                    user.user_permissions.remove(permission)

@receiver(m2m_changed, sender=User.groups.through)
def sync_user_group_permissions(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        # Get all permissions from all of the user's groups
        group_permissions = Permission.objects.filter(group__in=instance.groups.all()).distinct()
        
        # Add these permissions directly to the user's permissions
        for permission in group_permissions:
            instance.user_permissions.add(permission)

        # Remove any permissions that are no longer in any of the user's groups
        user_permissions = instance.user_permissions.all()
        for permission in user_permissions:
            if permission not in group_permissions:
                instance.user_permissions.remove(permission)