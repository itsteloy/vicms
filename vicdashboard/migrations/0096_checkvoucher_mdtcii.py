from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0095_merge_0094_conflict'),
    ]

    operations = [
        migrations.AlterField(
            model_name='checkvoucher',
            name='company',
            field=models.CharField(
                choices=[
                    ('mdspii', 'METRO DAVAO SUPREME PUMPS INDUSTRIES, INC.'),
                    ('versatec', 'VERSATEC INDUSTRIAL CORPORATION'),
                    ('mdtcii', 'METRO DAVAO TRADE & CONSTRUCTION INDUSTRIES, INC.'),
                ],
                db_index=True,
                default='mdspii',
                max_length=20,
            ),
        ),
    ]
