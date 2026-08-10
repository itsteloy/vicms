from django.db import migrations


def rename_ss_loan_to_sss_loan(apps, schema_editor):
    DeductionConfig = apps.get_model('vicdashboard', 'DeductionConfig')
    EmployeeDeduction = apps.get_model('vicdashboard', 'EmployeeDeduction')

    old = DeductionConfig.objects.filter(code='SS_LOAN').first()
    new = DeductionConfig.objects.filter(code='SSS_LOAN').first()

    if old and not new:
        old.code = 'SSS_LOAN'
        old.name = 'SSS Loan'
        old.save(update_fields=['code', 'name'])
        return

    if old and new:
        EmployeeDeduction.objects.filter(deduction_config=old).update(deduction_config=new)
        old.delete()


def revert_sss_loan_to_ss_loan(apps, schema_editor):
    DeductionConfig = apps.get_model('vicdashboard', 'DeductionConfig')
    row = DeductionConfig.objects.filter(code='SSS_LOAN').first()
    if row and not DeductionConfig.objects.filter(code='SS_LOAN').exists():
        row.code = 'SS_LOAN'
        row.save(update_fields=['code'])


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0054_payrollline_ot_hours'),
    ]

    operations = [
        migrations.RunPython(rename_ss_loan_to_sss_loan, revert_sss_loan_to_ss_loan),
    ]
