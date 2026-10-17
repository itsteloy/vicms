from decimal import Decimal

from django.db import migrations, models


def migrate_single_deduction_to_lines(apps, schema_editor):
    WeeklyReport = apps.get_model('vicdashboard', 'WaterWeeklyReport')
    DeductionLine = apps.get_model('vicdashboard', 'WaterWeeklyDeductionLine')
    for report in WeeklyReport.objects.all().only(
        'id', 'other_deduction_label', 'other_deduction_amount'
    ):
        label = (getattr(report, 'other_deduction_label', '') or '').strip()
        amount = getattr(report, 'other_deduction_amount', None) or Decimal('0.00')
        if amount and amount > Decimal('0.00'):
            DeductionLine.objects.create(
                report_id=report.id,
                line_no=1,
                label=label,
                amount=amount,
            )


def reverse_migrate_lines_to_single(apps, schema_editor):
    WeeklyReport = apps.get_model('vicdashboard', 'WaterWeeklyReport')
    DeductionLine = apps.get_model('vicdashboard', 'WaterWeeklyDeductionLine')
    for report in WeeklyReport.objects.all().only('id'):
        first = (
            DeductionLine.objects.filter(report_id=report.id)
            .order_by('line_no', 'id')
            .first()
        )
        if first:
            WeeklyReport.objects.filter(pk=report.id).update(
                other_deduction_label=first.label or '',
                other_deduction_amount=first.amount or Decimal('0.00'),
            )


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0093_waterweeklyreport_other_deduction'),
    ]

    operations = [
        migrations.CreateModel(
            name='WaterWeeklyDeductionLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('line_no', models.PositiveIntegerField(default=1)),
                ('label', models.CharField(blank=True, default='', max_length=120)),
                ('amount', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('report', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='deduction_lines', to='vicdashboard.waterweeklyreport')),
            ],
            options={
                'ordering': ['line_no', 'id'],
            },
        ),
        migrations.RunPython(
            migrate_single_deduction_to_lines,
            reverse_migrate_lines_to_single,
        ),
        migrations.RemoveField(
            model_name='waterweeklyreport',
            name='other_deduction_amount',
        ),
        migrations.RemoveField(
            model_name='waterweeklyreport',
            name='other_deduction_label',
        ),
    ]
