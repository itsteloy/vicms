from decimal import Decimal

from django.db import migrations


# Account numbers for customers whose registration install paid was audited
# but never written as WaterPayment.
BACKFILL_ACCOUNTS = {
    'WA-2026-409': Decimal('3000.00'),  # GIANGAN, FERDINAND (fee 5900 − bal 2900)
    'WA-2026-410': Decimal('5900.00'),  # RESMA, MARIA GLORIA (fee 5900 − bal 0)
}


def backfill_registration_installation_payments(apps, schema_editor):
    WaterCustomer = apps.get_model('vicdashboard', 'WaterCustomer')
    WaterPayment = apps.get_model('vicdashboard', 'WaterPayment')

    def next_receipt_number():
        year = __import__('datetime').date.today().year
        prefix = f'WP-{year}-'
        existing = (
            WaterPayment.objects.filter(receipt_number__startswith=prefix)
            .order_by('-receipt_number')
            .values_list('receipt_number', flat=True)
            .first()
        )
        if existing:
            try:
                n = int(str(existing).split('-')[-1])
            except (TypeError, ValueError):
                n = 0
        else:
            n = 0
        return f'{prefix}{n + 1:03d}'

    for account_number, amount in BACKFILL_ACCOUNTS.items():
        customer = WaterCustomer.objects.filter(account_number=account_number).first()
        if not customer:
            continue
        # Skip if any installation payment already exists — no duplicate collections.
        if WaterPayment.objects.filter(customer_id=customer.pk, purpose='installation').exists():
            continue
        WaterPayment.objects.create(
            receipt_number=next_receipt_number(),
            ar_number=None,
            bill=None,
            customer=customer,
            purpose='installation',
            payment_date=customer.registration_date,
            amount=amount,
            payment_method='cash',
            reference_number='',
            received_by='',
            remarks='Installation fee (customer registration)',
        )
        # Do NOT change installment_balance — already correct from registration.


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0083_mindanao_motors_rate_35'),
    ]

    operations = [
        migrations.RunPython(backfill_registration_installation_payments, noop_reverse),
    ]
