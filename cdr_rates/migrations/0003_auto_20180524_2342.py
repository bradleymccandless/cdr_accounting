# Generated by Django 2.0.5 on 2018-05-24 23:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cdr_rates', '0002_auto_20180524_0212'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='table',
            options={'verbose_name': 'rate', 'verbose_name_plural': 'rates'},
        ),
        migrations.AlterField(
            model_name='table',
            name='pulse',
            field=models.PositiveSmallIntegerField(default=60, verbose_name='Pulse'),
        ),
    ]