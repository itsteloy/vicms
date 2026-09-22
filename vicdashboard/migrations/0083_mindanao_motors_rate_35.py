from datetime import date
from decimal import Decimal

from django.db import migrations
from django.db.models import Q


TARGET_RATE = Decimal('35.00')
TARGET_NAME = 'MINDANAO MOTORS IMPORT CORP'
MIN_CHARGE = Decimal('100.00')
MIN_CHARGE_MAX_CUM = 5


def _normalize(value):
    return (value or '').strip().upper().rstrip('.').strip()


def _is_target_customer(customer):
    candidates = [
        customer.first_name,
        customer.last_name,
    ]
    last = (customer.last_name or '').strip()
    first = (customer.first_name or '').strip()
    if last and first:
        candidates.extend([
            f'{last}, {first}',
            f'{last} {first}',
            f'{first} {last}',
        ])
    for raw in candidates:
        key = _normalize(raw)
        if key == TARGET_NAME:
            return True
        if ',' in key:
            for part in key.split(','):
                if _normalize(part) == TARGET_NAME:
                    return True
    return False


def _consumption_charge(consumption, rate):
    consumption = int(consumption or 0)
    rate = Decimal(rate)
    if 0 <= consumption <= MIN_CHARGE_MAX_CUM:
        return MIN_CHARGE.quantize(Decimal('0.01'))
    return (Decimal(consumption) * rate).quantize(Decimal('0.01'))


def recalculate_mindanao_motors_bills(apps, schema_editor):
    WaterCustomer = apps.get_model('vicdashboard', 'WaterCustomer')
    WaterBill = apps.get_model('vicdashboard', 'WaterBill')

    customers = WaterCustomer.objects.filter(
        Q(first_name__icontains='MINDANAO MOTORS')
        | Q(last_name__icontains='MINDANAO MOTORS')
    )
    target_ids = [c.pk for c in customers if _is_target_customer(c)]
    if not target_ids:
        return

    today = date.today()
    bills = WaterBill.objects.filter(
        customer_id__in=target_ids,
        status__in=('unpaid', 'partial', 'overdue'),
    )
    for bill in bills:
        bill.rate_per_cum = TARGET_RATE
        bill.consumption_charge = _consumption_charge(bill.consumption, TARGET_RATE)
        bill.total_amount = (
            bill.consumption_charge
            + (bill.previous_bill_unpaid or Decimal('0'))
            + (bill.installment_balance or Decimal('0'))
            + (bill.fixed_charge or Decimal('0'))
            + (bill.environmental_fee or Decimal('0'))
            + (bill.maintenance_fee or Decimal('0'))
            + (bill.tax or Decimal('0'))
            + (bill.penalty or Decimal('0'))
            - (bill.discount or Decimal('0'))
        ).quantize(Decimal('0.01'))
        if bill.total_amount < 0:
            bill.total_amount = Decimal('0.00')

        paid = bill.amount_paid or Decimal('0.00')
        if bill.status != 'cancelled':
            if paid <= 0:
                bill.status = 'overdue' if bill.due_date and bill.due_date < today else 'unpaid'
            elif paid >= bill.total_amount:
                bill.status = 'paid'
            else:
                bill.status = 'partial'
        bill.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0082_water_weekly_report_default_signatories'),
    ]

    operations = [
        migrations.RunPython(recalculate_mindanao_motors_bills, noop_reverse),
    ]
