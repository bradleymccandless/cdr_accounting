# Generated by Django 2.0.3 on 2018-06-01 20:45

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cdr_rates', '0012_cachedrate'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='cachedrate',
            name='id',
        ),
        migrations.AlterField(
            model_name='cachedrate',
            name='accountcode',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='cdr_rates.Rate'),
        ),
    ]