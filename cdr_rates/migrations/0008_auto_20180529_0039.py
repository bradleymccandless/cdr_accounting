# Generated by Django 2.0.3 on 2018-05-29 00:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cdr_rates', '0007_auto_20180529_0036'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='CustomerRate',
            new_name='Rate',
        ),
    ]