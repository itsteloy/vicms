from decimal import Decimal

from django.db import migrations
from django.utils import timezone


ZERO = Decimal('0.00')
ACCOUNT_NUMBER = 'WA-2026-232'


def _water_only_net(bill):
    return (
        (bill.consumption_charge or ZERO)
        + (bill.fixed_charge or ZERO)
        + (bill.environmental_fee or ZERO)
        + (bill.maintenance_fee or ZERO)
        + (bill.tax or ZERO)
        + (bill.penalty or ZERO)
        - (bill.discount or ZERO)
        - (bill.amount_paid or ZERO)
    ).quantize(Decimal('0.01'))


def _bill_total(bill):
    return (
        (bill.consumption_charge or ZERO)
        + (bill.previous_bill_unpaid or ZERO)
        + (bill.installment_balance or ZERO)
        + (bill.fixed_charge or ZERO)
        + (bill.environmental_fee or ZERO)
        + (bill.maintenance_fee or ZERO)
        + (bill.tax or ZERO)
        + (bill.penalty or ZERO)
        - (bill.discount or ZERO)
    ).quantize(Decimal('0.01'))


def _bill_status(bill):
    total = bill.total_amount or ZERO
    paid = bill.amount_paid or ZERO
    if paid >= total:
        return 'paid'
    if paid <= ZERO:
        today = timezone.localdate()
        return 'overdue' if bill.due_date and bill.due_date < today else 'unpaid'
    return 'partial'


def fix_paid_water_carry(apps, schema_editor):
    WaterBill = apps.get_model('vicdashboard', 'WaterBill')
    WaterCustomer = apps.get_model('vicdashboard', 'WaterCustomer')
    WaterMeterReading = apps.get_model('vicdashboard', 'WaterMeterReading')

    customer = WaterCustomer.objects.filter(account_number=ACCOUNT_NUMBER).first()
    if customer is None:
        return

    bills = list(
        WaterBill.objects
        .filter(customer_id=customer.pk)
        .exclude(status='cancelled')
        .order_by('bill_date', 'pk')
    )
    if len(bills) < 2:
        return

    running = (
        (bills[0].previous_bill_unpaid or ZERO)
        + _water_only_net(bills[0])
    )

    for bill in bills[1:]:
        expected_previous = running
        changed = False

        if (bill.previous_bill_unpaid or ZERO) != expected_previous:
            bill.previous_bill_unpaid = expected_previous
            bill.total_amount = _bill_total(bill)
            bill.status = _bill_status(bill)
            bill.save(update_fields=[
                'previous_bill_unpaid', 'total_amount', 'status',
            ])
            changed = True

        if changed and bill.meter_reading_id:
            reading = WaterMeterReading.objects.filter(pk=bill.meter_reading_id).first()
            if reading and (reading.previous_bill_unpaid or ZERO) != expected_previous:
                reading.previous_bill_unpaid = expected_previous
                reading.save(update_fields=['previous_bill_unpaid'])

        running = expected_previous + _water_only_net(bill)


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0104_fix_negative_water_carry'),
    ]

    operations = [
        migrations.RunPython(fix_paid_water_carry, migrations.RunPython.noop),
    ]
