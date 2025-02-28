# Generated by Django 5.0.6 on 2024-09-24 12:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('purchase', '0003_vendor_profile_picture'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='purchaserequest',
            name='department',
        ),
        migrations.AddField(
            model_name='purchaserequest',
            name='can_edit',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='purchaserequest',
            name='is_submitted',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='purchaserequest',
            name='status',
            field=models.CharField(default='draft', max_length=20),
        ),
    ]
