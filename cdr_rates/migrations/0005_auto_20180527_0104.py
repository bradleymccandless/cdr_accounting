# Generated by Django 2.0.3 on 2018-05-27 01:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cdr_rates', '0004_auto_20180527_0053'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Table',
            new_name='Rate',
        ),
    ]