BEGIN;
TRUNCATE "django_content_type", "django_admin_log", "auth_permission", "auth_group",
         "registration_userprofile", "auth_group_permissions", "registration_domain",
         "auth_user_groups", "django_session", "auth_user", "registration_tenant",
         "auth_user_user_permissions" CASCADE;
COMMIT;
