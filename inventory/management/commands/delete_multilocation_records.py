from django.core.management.base import BaseCommand
from inventory.models import MultiLocation, Location
from django_tenants.utils import schema_context, get_tenant_model


class Command(BaseCommand):
    help = 'Deletes all records of MultiLocation in all schemas except public'

    def handle(self, *args, **options):
        tenant_model = get_tenant_model()
        schemas = tenant_model.objects.values_list('schema_name', flat=True).exclude(schema_name='public')

        for schema_name in schemas:
            self.stdout.write(self.style.NOTICE(f'Processing schema: {schema_name}'))
            with schema_context(schema_name):
                deleted_multilocation_count, _ = MultiLocation.objects.all().delete()
                deleted_location_count, _ = Location.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(
                    f'Deleted {deleted_multilocation_count} MultiLocation records and {deleted_location_count}'
                    f'Location records in schema {schema_name}'))
