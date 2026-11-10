from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0100_waterservicecontract_ack_ar_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='checkvoucher',
            name='liquidation_status',
            field=models.CharField(
                choices=[('unliquidated', 'Unliquidated'), ('liquidated', 'Liquidated')],
                db_index=True,
                default='unliquidated',
                max_length=20,
            ),
        ),
    ]
