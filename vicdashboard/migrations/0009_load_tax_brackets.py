from django.db import migrations

def load_tax_brackets(apps, schema_editor):
    TaxBracket = apps.get_model('vicdashboard', 'TaxBracket')
    # Withholding Tax (2026 TRAIN Law rates – simplified)
    withholding_brackets = [
        {'min': 0, 'max': 250000, 'base': 0, 'rate': 0.15},
        {'min': 250000, 'max': 400000, 'base': 0, 'rate': 0.20},
        {'min': 400000, 'max': 800000, 'base': 0, 'rate': 0.25},
        {'min': 800000, 'max': 2000000, 'base': 0, 'rate': 0.30},
        {'min': 2000000, 'max': 8000000, 'base': 0, 'rate': 0.35},
        {'min': 8000000, 'max': None, 'base': 0, 'rate': 0.35},  # adjust as needed
    ]
    effective_date = '2026-01-01'
    for bracket in withholding_brackets:
        TaxBracket.objects.create(
            effective_date=effective_date,
            min_amount=bracket['min'],
            max_amount=bracket['max'],
            base_tax=bracket['base'],
            tax_rate=bracket['rate'],
            tax_type='withholding'
        )

    # SSS contributions (2026 rates – simplified as percentage of salary)
    # Actually SSS has fixed brackets per salary, but we'll use a simplified percentage.
    # In reality, you'd have multiple brackets for SSS.
    sss_rate = 0.045  # 4.5% employee share
    TaxBracket.objects.create(
        effective_date=effective_date,
        min_amount=0,
        max_amount=None,
        base_tax=0,
        tax_rate=sss_rate,
        tax_type='sss'
    )

    # PhilHealth (2026 rate: 4% of salary, split equally with employer, employee pays 2%)
    philhealth_rate = 0.02  # employee share
    TaxBracket.objects.create(
        effective_date=effective_date,
        min_amount=0,
        max_amount=None,
        base_tax=0,
        tax_rate=philhealth_rate,
        tax_type='philhealth'
    )

    # Pag‑IBIG (2026: ₱100 fixed for employees earning > ₱1500)
    # We'll use a fixed amount approach; you can store as fixed_amount field if needed.
    # For simplicity, we'll store as tax_rate = 0, and handle in code.
    # Or we can create a separate config for Pag‑IBIG.
    # We'll use a percentage approximation.
    pagibig_rate = 0.01  # 1% (but capped at ₱100)
    TaxBracket.objects.create(
        effective_date=effective_date,
        min_amount=0,
        max_amount=None,
        base_tax=0,
        tax_rate=pagibig_rate,
        tax_type='pagibig'
    )

def reverse_load_tax_brackets(apps, schema_editor):
    TaxBracket = apps.get_model('vicdashboard', 'TaxBracket')
    TaxBracket.objects.filter(
        effective_date='2026-01-01',
        tax_type__in=['withholding', 'sss', 'philhealth', 'pagibig']
    ).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('vicdashboard', '0008_holiday_leaverequest_shiftschedule_attendancelog_and_more'),  # Replace with the actual last migration file
    ]
    operations = [
        migrations.RunPython(load_tax_brackets, reverse_load_tax_brackets),
    ]