# Generated by Django 2.0.5 on 2018-05-24 02:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cdr_rates', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Rate',
            new_name='Table',
        ),
        migrations.AlterModelOptions(
            name='table',
            options={'verbose_name': 'Customer Rate Table', 'verbose_name_plural': 'Customer Rate Table'},
        ),
    ]
