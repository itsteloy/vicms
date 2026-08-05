# Rename Department→Company and remove salary fields

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0046_employee_company_remove_salary'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Department',
            new_name='Company',
        ),
        migrations.RenameField(
            model_name='employee',
            old_name='department',
            new_name='company',
        ),
        migrations.RemoveField(
            model_name='employee',
            name='base_salary',
        ),
        migrations.RemoveField(
            model_name='employee',
            name='salary_frequency',
        ),
        migrations.AlterField(
            model_name='employee',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='vicdashboard.company'),
        ),
        migrations.AlterField(
            model_name='employee',
            name='daily_rate',
            field=models.DecimalField(
                decimal_places=2,
                default=525,
                help_text='Daily wage used for payroll and idle-day estimates (default ₱525).',
                max_digits=12,
            ),
        ),
    ]
