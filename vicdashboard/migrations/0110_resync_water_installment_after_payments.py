from decimal import Decimal

from django.db import migrations
from django.utils import timezone


ZERO = Decimal('0.00')


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


def resync_installment_balance(apps, schema_editor):
    """Repair stale installment snapshots left by installment payments.

    Installation payments reduce ``customer.installment_balance`` but (before
    this fix) did not re-sync the latest bill/reading snapshot, so the Bills
    table and Statement of Account kept the pre-payment ``installment_balance``
    while Account Information showed the reduced balance. This re-syncs the
    latest non-cancelled bill and latest reading to the customer's current
    balance and recomputes totals/status. Older bills stay as historical
    snapshots.
    """
    WaterBill = apps.get_model('vicdashboard', 'WaterBill')
    WaterCustomer = apps.get_model('vicdashboard', 'WaterCustomer')
    WaterMeterReading = apps.get_model('vicdashboard', 'WaterMeterReading')

    customer_ids = (
        WaterCustomer.objects.filter(bills__isnull=False)
        .values_list('pk', flat=True)
        .distinct()
    )

    for customer_id in customer_ids:
        customer = WaterCustomer.objects.filter(pk=customer_id).first()
        if not customer:
            continue
        bal = customer.installment_balance or ZERO

        reading = (
            WaterMeterReading.objects
            .filter(customer_id=customer_id)
            .order_by('-reading_date', '-pk')
            .first()
        )
        if reading and (reading.installment_balance or ZERO) != bal:
            reading.installment_balance = bal
            reading.save(update_fields=['installment_balance'])

        bill = (
            WaterBill.objects
            .filter(customer_id=customer_id)
            .exclude(status='cancelled')
            .order_by('-bill_date', '-pk')
            .first()
        )
        if bill and (bill.installment_balance or ZERO) != bal:
            bill.installment_balance = bal
            bill.total_amount = _bill_total(bill)
            bill.status = _bill_status(bill)
            bill.save(update_fields=[
                'installment_balance', 'total_amount', 'status',
            ])


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0109_fix_wa2026_088_august_payment'),
    ]

    operations = [
        migrations.RunPython(resync_installment_balance, migrations.RunPython.noop),
    ]
