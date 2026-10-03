# Generated for check voucher withholding tax row

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0090_waterbill_print_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='checkvoucher',
            name='withholding_tax',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name='checkvoucher',
            name='withholding_label',
            field=models.CharField(blank=True, default='WITHHOLDING TAX', max_length=120),
        ),
    ]
