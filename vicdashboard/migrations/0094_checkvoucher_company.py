from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0093_waterweeklyreport_other_deduction'),
    ]

    operations = [
        migrations.AddField(
            model_name='checkvoucher',
            name='company',
            field=models.CharField(
                choices=[
                    ('mdspii', 'METRO DAVAO SUPREME PUMPS INDUSTRIES, INC.'),
                    ('versatec', 'VERSATEC INDUSTRIAL CORPORATION'),
                ],
                db_index=True,
                default='mdspii',
                max_length=20,
            ),
        ),
    ]
