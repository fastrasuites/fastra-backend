from django.core.management.base import BaseCommand
from inventory.models import MultiLocation, Location
from django_tenants.utils import schema_context, get_tenant_model


class Command(BaseCommand):
    help = 'Deletes all records of Location in a specified schema except public'

    def add_arguments(self, parser):
        parser.add_argument(
            'schema_name',
            type=str,
            help='The schema name to process (excluding "public")'
        )

    def handle(self, *args, **options):
        tenant_model = get_tenant_model()
        schemas = tenant_model.objects.values_list('schema_name', flat=True).exclude(schema_name='public')

        schema_name = options['schema_name']  # Run with the specific schema name
        if schema_name not in schemas or schema_name == 'public':
            self.stdout.write(self.style.ERROR(f'The schema name "{schema_name}" does not exist.'))
            return
        self.stdout.write(self.style.NOTICE(f'Processing schema: {schema_name}'))
        with schema_context(schema_name):
            multilocation = MultiLocation.objects.all().exists()
            deleted_location_count, _ = Location.objects.all().delete()
            if multilocation and deleted_location_count > 0:
                self.stdout.write(self.style.SUCCESS(
                    f'Deleted {deleted_location_count} Location records in schema {schema_name}'))
            else:
                self.stdout.write(self.style.NOTICE(
                    f'No Location records found in schema {schema_name}'))
