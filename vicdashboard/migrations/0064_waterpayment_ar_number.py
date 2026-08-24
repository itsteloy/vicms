from django.db import migrations, models


def copy_bill_ar_to_payments(apps, schema_editor):
    WaterPayment = apps.get_model('vicdashboard', 'WaterPayment')
    used = set(
        WaterPayment.objects.exclude(ar_number__isnull=True).exclude(ar_number='').values_list('ar_number', flat=True)
    )
    for payment in WaterPayment.objects.select_related('bill').iterator():
        if payment.ar_number:
            continue
        bill_ar = (getattr(payment.bill, 'ar_number', None) or '').strip()
        if not bill_ar or bill_ar in used:
            continue
        WaterPayment.objects.filter(pk=payment.pk).update(ar_number=bill_ar)
        used.add(bill_ar)


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0063_waterbill_ar_number_manual'),
    ]

    operations = [
        migrations.AddField(
            model_name='waterpayment',
            name='ar_number',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
        migrations.RunPython(copy_bill_ar_to_payments, migrations.RunPython.noop),
    ]
