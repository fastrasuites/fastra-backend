from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from registration.models import Domain
from .models import Tenant


class DomainInline(admin.TabularInline):
    model = Domain
    max_num = 1


@admin.register(Tenant)
class TenantAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('schema_name', 'created_on', )
    inlines = [DomainInline]
