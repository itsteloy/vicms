from datetime import date

from django.db import migrations


DEDUCTIONS = [
    {
        'code': 'PHILHEALTH',
        'name': 'PhilHealth Contribution',
        'type': 'statutory',
    },
    {
        'code': 'SSS',
        'name': 'SSS Contribution',
        'type': 'statutory',
    },
    {
        'code': 'HDMF',
        'name': 'HDMF Contribution',
        'type': 'statutory',
    },
    {
        'code': 'SSS_LOAN',
        'name': 'SSS Loan',
        'type': 'loan',
    },
    {
        'code': 'HDMF_LOAN',
        'name': 'HDMF Loan',
        'type': 'loan',
    },
]


def seed_payroll_deductions(apps, schema_editor):
    DeductionConfig = apps.get_model('vicdashboard', 'DeductionConfig')
    effective = date(2026, 1, 1)
    for item in DEDUCTIONS:
        DeductionConfig.objects.update_or_create(
            code=item['code'],
            defaults={
                'name': item['name'],
                'type': item['type'],
                'fixed_amount': 0,
                'percentage_of_gross': 0,
                'is_active': True,
                'effective_date': effective,
                'end_date': None,
            },
        )


def unseed_payroll_deductions(apps, schema_editor):
    DeductionConfig = apps.get_model('vicdashboard', 'DeductionConfig')
    DeductionConfig.objects.filter(
        code__in=[item['code'] for item in DEDUCTIONS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0050_payrollrun_attendance_sheets'),
    ]

    operations = [
        migrations.RunPython(seed_payroll_deductions, unseed_payroll_deductions),
    ]
