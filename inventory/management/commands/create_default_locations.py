from django.core.management.base import BaseCommand
from inventory.models import Location, MultiLocation

class Command(BaseCommand):
    help = 'Creates two default Location instances and a multiLocation instance'

    def handle(self, *args, **options):
        settings = MultiLocation.objects.create(
            is_activated=False
        )

        self.stdout.write(self.style.SUCCESS(f'Created MultiLocation option: Set to {settings}'))

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
        self.stdout.write(self.style.SUCCESS(f'Created Location: {location1}'))

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
        self.stdout.write(self.style.SUCCESS(f'Created Location: {location2}'))

        settings = MultiLocation.objects.create(
            is_activated=False
        )

        self.stdout.write(self.style.SUCCESS(f'MultiLocation is set to {settings}'))