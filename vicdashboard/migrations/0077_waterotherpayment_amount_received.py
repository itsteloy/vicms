from decimal import Decimal

from django.db import migrations, models


def backfill_amount_received(apps, schema_editor):
    WaterOtherPayment = apps.get_model('vicdashboard', 'WaterOtherPayment')
    for payment in WaterOtherPayment.objects.filter(amount_received__isnull=True):
        WaterOtherPayment.objects.filter(pk=payment.pk).update(amount_received=payment.amount or Decimal('0.00'))


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0076_waterotherpayment'),
    ]

    operations = [
        migrations.AddField(
            model_name='waterotherpayment',
            name='amount_received',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Actual amount received; editable on the weekly report.',
                max_digits=14,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_amount_received, migrations.RunPython.noop),
    ]
