from datetime import date

from django.db import migrations


HDMF_LOAN = {
    'code': 'HDMF_LOAN',
    'name': 'HDMF Loan',
    'type': 'loan',
}


def seed_hdmf_loan(apps, schema_editor):
    DeductionConfig = apps.get_model('vicdashboard', 'DeductionConfig')
    DeductionConfig.objects.update_or_create(
        code=HDMF_LOAN['code'],
        defaults={
            'name': HDMF_LOAN['name'],
            'type': HDMF_LOAN['type'],
            'fixed_amount': 0,
            'percentage_of_gross': 0,
            'is_active': True,
            'effective_date': date(2026, 1, 1),
            'end_date': None,
        },
    )


def unseed_hdmf_loan(apps, schema_editor):
    DeductionConfig = apps.get_model('vicdashboard', 'DeductionConfig')
    DeductionConfig.objects.filter(code=HDMF_LOAN['code']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0051_seed_payroll_deduction_configs'),
    ]

    operations = [
        migrations.RunPython(seed_hdmf_loan, unseed_hdmf_loan),
    ]
