# Generated by Django 2.0.3 on 2018-05-27 00:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cdr_rates', '0003_auto_20180524_2342'),
    ]

    operations = [
        migrations.AlterField(
            model_name='table',
            name='canadian_ld_rate',
            field=models.DecimalField(decimal_places=4, default=0.02, max_digits=5, verbose_name='Canadian Long Distance Rate'),
        ),
        migrations.AlterField(
            model_name='table',
            name='inbound_rate',
            field=models.DecimalField(decimal_places=4, default=0.02, max_digits=5, verbose_name='Inbound Calling Rate'),
        ),
        migrations.AlterField(
            model_name='table',
            name='inbound_tollfree_rate',
            field=models.DecimalField(decimal_places=4, default=0.03, max_digits=5, verbose_name='Inbound Tollfree Calling Rate'),
        ),
        migrations.AlterField(
            model_name='table',
            name='international_ld_rate',
            field=models.DecimalField(decimal_places=4, default=0.02, max_digits=5, verbose_name='International Long Distance Rate'),
        ),
        migrations.AlterField(
            model_name='table',
            name='outbound_rate',
            field=models.DecimalField(decimal_places=4, default=0.02, max_digits=5, verbose_name='Outbound Calling Rate'),
        ),
        migrations.AlterField(
            model_name='table',
            name='united_states_ld_rate',
            field=models.DecimalField(decimal_places=4, default=0.02, max_digits=5, verbose_name='American Long Distance Rate'),
        ),
    ]
