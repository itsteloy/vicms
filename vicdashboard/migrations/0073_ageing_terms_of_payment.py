# Generated manually for Ageing of Accounts Terms of Payment

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0072_petty_cash_report'),
    ]

    operations = [
        migrations.AddField(
            model_name='ageingofaccountsline',
            name='terms_of_payment',
            field=models.CharField(
                blank=True,
                choices=[
                    ('7', '7 days'),
                    ('15', '15 days'),
                    ('30', '30 days'),
                    ('60', '60 days'),
                ],
                default='',
                max_length=10,
            ),
        ),
    ]
