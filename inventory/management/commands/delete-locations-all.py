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
            try:
                with schema_context(schema_name):
                    multilocation = MultiLocation.objects.all().exists()
                    deleted_location_count, _ = Location.objects.all().delete()
                    if multilocation and deleted_location_count > 0:
                        self.stdout.write(self.style.SUCCESS(
                            f'Deleted {deleted_location_count} Location records in schema {schema_name}'))
                    else:
                        self.stdout.write(self.style.NOTICE(
                            f'No Location records found in schema {schema_name}'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f'Error processing schema {schema_name}: {e}'))
