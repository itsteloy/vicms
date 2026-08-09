from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0049_inventory_category_nested'),
    ]

    operations = [
        migrations.AddField(
            model_name='payrollrun',
            name='use_attendance_sheets',
            field=models.BooleanField(
                default=True,
                help_text='Apply undertime/absence deductions from biometric attendance sheets.',
            ),
        ),
        migrations.AddField(
            model_name='payrollrun',
            name='attendance_sheet_ids',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
