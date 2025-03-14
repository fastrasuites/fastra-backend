# Generated by Django 5.0.6 on 2024-10-18 08:04

import django.db.models.deletion
import django_ckeditor_5.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('purchase', '0007_alter_product_product_category_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('currency_name', models.CharField(max_length=100)),
                ('currency_symbol', django_ckeditor_5.fields.CKEditor5Field(blank=True, null=True)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('is_hidden', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name_plural': 'Currencies',
                'ordering': ['is_hidden', '-created_on'],
            },
        ),
        migrations.RenameField(
            model_name='unitofmeasure',
            old_name='name',
            new_name='unit_category',
        ),
        migrations.RemoveField(
            model_name='unitofmeasure',
            name='description',
        ),
        migrations.AddField(
            model_name='purchaseorder',
            name='can_edit',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='purchaseorder',
            name='created_by',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='purchase_orders', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='purchaseorder',
            name='delivery_terms',
            field=models.CharField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='purchaseorder',
            name='is_submitted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='purchaseorder',
            name='payment_terms',
            field=models.CharField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='purchaseorder',
            name='purchase_policy',
            field=models.CharField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='purchaseorderitem',
            name='unit_of_measure',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='purchase_orders', to='purchase.unitofmeasure'),
        ),
        migrations.AddField(
            model_name='unitofmeasure',
            name='unit_name',
            field=models.CharField(default='Unknown', max_length=100),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='purchaseorder',
            name='vendor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='purchase_orders', to='purchase.vendor'),
        ),
        migrations.AddField(
            model_name='purchaseorder',
            name='currency',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='purchase_orders', to='purchase.currency'),
        ),
    ]
