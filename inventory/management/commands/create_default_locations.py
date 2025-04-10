from django.core.management.base import BaseCommand
from inventory.models import Location, MultiLocation
from django_tenants.utils import schema_context, get_tenant_model

class Command(BaseCommand):
    help = 'Creates default Location instances and a MultiLocation instance for all schemas except public'

    def handle(self, *args, **options):
        tenant_model = get_tenant_model()
        schemas = tenant_model.objects.values_list('schema_name', flat=True).exclude(schema_name='public')

        for schema_name in schemas:
            self.stdout.write(self.style.NOTICE(f'Processing schema: {schema_name}'))
            with schema_context(schema_name):
                settings = MultiLocation.objects.create(
                    is_activated=False
                )
                self.stdout.write(self.style.SUCCESS(f'Created MultiLocation option in schema {schema_name}: {settings}'))

                # Create the first Location instance
                location1 = Location.objects.create(
                    id="SUPP00001",
                    id_number=1,
                    location_code="SUPP",
                    location_name="Supplier Location",
                    location_type="partner",
                    address="NullAddress",
                    location_manager=None,
                    store_keeper=None,
                    contact_information=""
                )
                self.stdout.write(self.style.SUCCESS(f'Created Location in schema {schema_name}: {location1}'))

                # Create the second Location instance
                location2 = Location.objects.create(
                    id="CUST00002",
                    id_number=2,
                    location_code="CUST",
                    location_name="Customer Location",
                    location_type="partner",
                    address="NullAddress",
                    location_manager=None,
                    store_keeper=None,
                    contact_information=""
                )
                self.stdout.write(self.style.SUCCESS(f'Created Location in schema {schema_name}: {location2}'))