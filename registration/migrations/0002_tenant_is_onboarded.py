# Generated by Django 5.0.6 on 2025-07-07 15:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='is_onboarded',
            field=models.BooleanField(default=False),
        ),
    ]
