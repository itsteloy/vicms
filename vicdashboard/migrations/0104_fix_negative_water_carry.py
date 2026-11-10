from decimal import Decimal

from django.db import migrations
from django.utils import timezone


ZERO = Decimal('0.00')


def _water_only_net(bill):
    return (
        (bill.consumption_charge or ZERO)
        + (bill.previous_bill_unpaid or ZERO)
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


def fix_negative_water_carry(apps, schema_editor):
    WaterBill = apps.get_model('vicdashboard', 'WaterBill')
    WaterCustomer = apps.get_model('vicdashboard', 'WaterCustomer')
    WaterMeterReading = apps.get_model('vicdashboard', 'WaterMeterReading')

    customer_ids = (
        WaterBill.objects
        .exclude(status='cancelled')
        .filter(previous_bill_unpaid__lt=ZERO)
        .values_list('customer_id', flat=True)
        .distinct()
    )

    for customer_id in customer_ids:
        bills = list(
            WaterBill.objects
            .filter(customer_id=customer_id)
            .exclude(status='cancelled')
            .order_by('bill_date', 'pk')
        )
        start = next(
            (index for index, bill in enumerate(bills)
             if (bill.previous_bill_unpaid or ZERO) < ZERO),
            None,
        )
        if start is None or start + 1 >= len(bills):
            continue

        previous_bill = bills[start]
        for bill in bills[start + 1:]:
            expected_previous = _water_only_net(previous_bill)
            if expected_previous >= ZERO:
                break

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

            previous_bill = bill

        latest_net = _water_only_net(bills[-1])
        if latest_net < ZERO:
            customer = WaterCustomer.objects.filter(pk=customer_id).first()
            if customer and (customer.previous_unpaid_balance or ZERO) < ZERO:
                customer.previous_unpaid_balance = latest_net
                customer.save(update_fields=['previous_unpaid_balance'])


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0103_watersalessummaryexclusion'),
    ]

    operations = [
        migrations.RunPython(fix_negative_water_carry, migrations.RunPython.noop),
    ]
