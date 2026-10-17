from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0092_checkvouchercreditline'),
    ]

    operations = [
        migrations.AddField(
            model_name='waterweeklyreport',
            name='other_deduction_amount',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14),
        ),
        migrations.AddField(
            model_name='waterweeklyreport',
            name='other_deduction_label',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
    ]
