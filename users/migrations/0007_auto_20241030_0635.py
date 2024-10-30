from django.db import migrations
from django.contrib.auth.models import Group

def create_roles(apps, schema_editor):
    role_names = ["Admin", "Accountant", "Manager", "HR", "Sales", "Employee"]
    for role in role_names:
        Group.objects.get_or_create(name=role)
class Migration(migrations.Migration):
    dependencies = [
        ('users', '0006_delete_grouppermission'),
    ]

    operations = [
        migrations.RunPython(create_roles),
    ]