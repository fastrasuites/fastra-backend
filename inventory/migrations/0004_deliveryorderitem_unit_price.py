# Generated by Django 5.0.6 on 2025-07-02 16:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliveryorderitem',
            name='unit_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Product Unit Price'),
        ),
    ]
