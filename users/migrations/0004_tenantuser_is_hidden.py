# Generated by Django 5.0.6 on 2024-09-17 14:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_remove_tenantuser_role_tenantuser_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantuser',
            name='is_hidden',
            field=models.BooleanField(default=False),
        ),
    ]