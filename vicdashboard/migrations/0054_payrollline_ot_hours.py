from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0053_leavebalance_sil_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='payrollline',
            name='ot_reg_hours',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name='payrollline',
            name='ot_sun_hours',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
    ]
