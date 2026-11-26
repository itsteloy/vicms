from datetime import date
from decimal import Decimal

from django.db import migrations
from django.utils import timezone


ZERO = Decimal('0.00')
ACCOUNT_NUMBER = 'WA-2026-088'
BILL_NUMBER = 'WB-2026-125'
PAYMENT_AMOUNT = Decimal('220.00')
PAYMENT_DATE = date(2026, 9, 12)
PAYMENT_METHOD = 'cash'
RECEIVED_BY = 'Aiza Poquita'


def _net_water(bill):
    """Water-only net for one bill: current charges/fees minus amount paid."""
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


def _total(bill):
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


def _status(total, paid, due_date):
    if paid >= total:
        return 'paid'
    if paid <= ZERO:
        today = timezone.localdate()
        return 'overdue' if due_date and due_date < today else 'unpaid'
    return 'partial'


def _next_receipt_number(WaterPayment):
    prefix = f'WP-{PAYMENT_DATE.year}-'
    max_num = 0
    for value in (
        WaterPayment.objects
        .filter(receipt_number__startswith=prefix)
        .values_list('receipt_number', flat=True)
    ):
        suffix = value[len(prefix):]
        if suffix.isdigit():
            max_num = max(max_num, int(suffix))
    return f'{prefix}{max_num + 1:03d}'


def fix_wa2026_088_august_payment(apps, schema_editor):
    """Record the missing August payment for WA-2026-088 and clear its carry.

    WB-2026-125 was paid by the customer on 2026-09-12 but the collection was
    never encoded, so its 220.00 balance was carried into the September and
    October statements as previous_bill_unpaid and reported as outstanding.

    Creates the WaterPayment record, marks the bill paid, then recalculates
    every later statement's previous_bill_unpaid snapshot from the ledger
    (opening carry + charges - payments) so the same pesos are not billed
    twice. Idempotent: re-running does not duplicate the payment.
    """
    WaterCustomer = apps.get_model('vicdashboard', 'WaterCustomer')
    WaterBill = apps.get_model('vicdashboard', 'WaterBill')
    WaterPayment = apps.get_model('vicdashboard', 'WaterPayment')
    WaterMeterReading = apps.get_model('vicdashboard', 'WaterMeterReading')
    WaterAuditLog = apps.get_model('vicdashboard', 'WaterAuditLog')

    customer = WaterCustomer.objects.filter(account_number=ACCOUNT_NUMBER).first()
    if customer is None:
        return

    bill = (
        WaterBill.objects
        .filter(customer=customer, bill_number=BILL_NUMBER)
        .exclude(status='cancelled')
        .first()
    )
    if bill is None:
        return

    already_recorded = WaterPayment.objects.filter(
        bill=bill,
        amount=PAYMENT_AMOUNT,
        payment_date=PAYMENT_DATE,
    ).exists()

    if not already_recorded and (bill.amount_paid or ZERO) < (bill.total_amount or ZERO):
        receipt_number = _next_receipt_number(WaterPayment)
        WaterPayment.objects.create(
            receipt_number=receipt_number,
            ar_number=None,
            bill=bill,
            customer=customer,
            purpose='bill',
            payment_date=PAYMENT_DATE,
            amount=PAYMENT_AMOUNT,
            payment_method=PAYMENT_METHOD,
            received_by=RECEIVED_BY,
            remarks='AUGUST',
        )
        bill.amount_paid = (bill.amount_paid or ZERO) + PAYMENT_AMOUNT
        bill.total_amount = _total(bill)
        bill.status = _status(
            bill.total_amount,
            bill.amount_paid,
            bill.due_date,
        )
        bill.save(update_fields=['amount_paid', 'total_amount', 'status'])
        WaterAuditLog.objects.create(
            username='system',
            action='Corrected billing record',
            entity_type='WaterBill',
            entity_id=str(BILL_NUMBER),
            details=(
                f'{ACCOUNT_NUMBER} {BILL_NUMBER}: recorded missing '
                f'{PAYMENT_AMOUNT} payment dated {PAYMENT_DATE.isoformat()} '
                f'(receipt {receipt_number}); cleared downstream prev-unpaid carry.'
            ),
        )

    bills = list(
        WaterBill.objects
        .filter(customer=customer)
        .exclude(status='cancelled')
        .order_by('bill_date', 'pk')
    )
    if len(bills) < 2:
        return

    running = (bills[0].previous_bill_unpaid or ZERO) + _net_water(bills[0])
    for later in bills[1:]:
        expected_previous = running
        changed = False
        if (later.previous_bill_unpaid or ZERO) != expected_previous:
            later.previous_bill_unpaid = expected_previous
            changed = True
        # Total must be recomputed AFTER the carry snapshot is corrected.
        new_total = _total(later)
        new_status = _status(new_total, later.amount_paid, later.due_date)
        if (later.total_amount or ZERO) != new_total:
            later.total_amount = new_total
            changed = True
        if later.status != new_status:
            later.status = new_status
            changed = True
        if changed:
            later.save(update_fields=[
                'previous_bill_unpaid', 'total_amount', 'status',
            ])
            reading = WaterMeterReading.objects.filter(pk=later.meter_reading_id).first()
            if reading and (reading.previous_bill_unpaid or ZERO) != expected_previous:
                reading.previous_bill_unpaid = expected_previous
                reading.save(update_fields=['previous_bill_unpaid'])
        running = expected_previous + _net_water(later)


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0108_sync_water_installment_balance'),
    ]

    operations = [
        migrations.RunPython(fix_wa2026_088_august_payment, migrations.RunPython.noop),
    ]
