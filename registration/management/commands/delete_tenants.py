from django.core.management.base import BaseCommand
from django.db import connection
from django.core.management import call_command

from registration.models import Tenant


class Command(BaseCommand):
    help = "Flush the public schema and all tenant schemas"

    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            # Temporarily disable constraints
            self.stdout.write("Disabling constraints...")
            cursor.execute("SET session_replication_role = 'replica';")

            # Flush public schema
            self.stdout.write("Flushing the public schema...")
            connection.set_schema_to_public()
            call_command('flush', '--no-input')

            # Flush tenant schemas
            self.stdout.write("Flushing tenant schemas...")
            for tenant in Tenant.objects.all():
                schema_name = tenant.schema_name
                self.stdout.write(f"Flushing tenant schema: {schema_name}")
                connection.set_schema(schema_name)
                call_command('flush', '--no-input')

            # Re-enable constraints
            self.stdout.write("Re-enabling constraints...")
            cursor.execute("SET session_replication_role = 'origin';")

        self.stdout.write("Flushing completed for all schemas.")
