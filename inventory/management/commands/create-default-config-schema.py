from django.core.management.base import BaseCommand
from purchase.models import UnitOfMeasure, Currency
from inventory.models import Location, MultiLocation
from django_tenants.utils import schema_context, get_tenant_model

class Command(BaseCommand):
    help = ('Creates default Location instances and ensures a MultiLocation instance exists for a specified schema '
            'other than public')

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
            # Use get_or_create for MultiLocation
            try:
                # Use get_or_create for MultiLocation
                multi_location, created = MultiLocation.objects.get_or_create(
                    id=1, defaults={'is_activated': False}
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Created MultiLocation option in schema {schema_name}: {multi_location}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'MultiLocation already exists in schema {schema_name}: {multi_location}'
                        )
                    )
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Error with MultiLocation in schema {schema_name}: {e}'))

            try:
                # Create the first Location instance
                location1 = Location.objects.create(
                    location_code="SUPP",
                    location_name="Supplier Location",
                    location_type="partner",
                    address="NullAddress",
                    location_manager=None,
                    store_keeper=None,
                    contact_information=""
                )
                self.stdout.write(self.style.SUCCESS(f'Created Location in schema {schema_name}: {location1}'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Error creating Supplier Location in schema {schema_name}: {e}'))

            try:
                # Create the second Location instance
                location2 = Location.objects.create(
                    location_code="CUST",
                    location_name="Customer Location",
                    location_type="partner",
                    address="NullAddress",
                    location_manager=None,
                    store_keeper=None,
                    contact_information=""
                )
                self.stdout.write(self.style.SUCCESS(f'Created Location in schema {schema_name}: {location2}'))
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(
                        f'Error creating Customer Location in schema {schema_name}: {e}'
                    )
                )

            try:
                unit_of_measure1 = UnitOfMeasure.objects.create(
                    unit_name="Kilogram",
                    unit_symbol="kg",
                    unit_category="Weight",
                )
                unit_of_measure2 = UnitOfMeasure.objects.create(
                    unit_name="Meter",
                    unit_symbol="m",
                    unit_category="Length",
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created UnitOfMeasure in schema {schema_name}: {unit_of_measure1}, {unit_of_measure2}'
                    )
                )
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Error creating UnitOfMeasure in schema {schema_name}: {e}'))

            try:
                currency1 = Currency.objects.create(
                    currency_name="US Dollar",
                    currency_code="USD",
                    currency_symbol="$",
                )

                currency2 = Currency.objects.create(
                    currency_name="Euro",
                    currency_code="EUR",
                    currency_symbol="€",
                )

                currency3 = Currency.objects.create(
                    currency_name="Naira",
                    currency_code="NGN",
                    currency_symbol="₦",
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created Currency in schema {schema_name}: {currency1}, {currency2}, {currency3}'
                    )
                )
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Error creating Currency in schema {schema_name}: {e}'))