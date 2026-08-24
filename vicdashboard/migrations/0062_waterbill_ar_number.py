from collections import defaultdict
from datetime import date

from django.db import migrations, models


def backfill_ar_numbers(apps, schema_editor):
    WaterBill = apps.get_model('vicdashboard', 'WaterBill')
    counters = defaultdict(int)
    for bill in WaterBill.objects.order_by('id'):
        year = bill.bill_date.year if bill.bill_date else date.today().year
        counters[year] += 1
        WaterBill.objects.filter(pk=bill.pk).update(ar_number=f'AR-{year}-{counters[year]:03d}')


def unfill_ar_numbers(apps, schema_editor):
    WaterBill = apps.get_model('vicdashboard', 'WaterBill')
    WaterBill.objects.update(ar_number='')


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0061_waterservicecontract'),
    ]

    operations = [
        migrations.AddField(
            model_name='waterbill',
            name='ar_number',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.RunPython(backfill_ar_numbers, unfill_ar_numbers),
        migrations.AlterField(
            model_name='waterbill',
            name='ar_number',
            field=models.CharField(blank=True, default='', max_length=50, unique=True),
        ),
    ]
