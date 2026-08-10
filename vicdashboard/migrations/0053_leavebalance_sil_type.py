from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0052_seed_hdmf_loan_deduction'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leavebalance',
            name='leave_type',
            field=models.CharField(
                choices=[
                    ('vacation', 'Vacation Leave'),
                    ('sick', 'Sick Leave'),
                    ('emergency', 'Emergency Leave'),
                    ('sil', 'SIL'),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='leaverequest',
            name='leave_type',
            field=models.CharField(
                choices=[
                    ('vacation', 'Vacation Leave'),
                    ('sick', 'Sick Leave'),
                    ('emergency', 'Emergency Leave'),
                    ('sil', 'SIL'),
                ],
                max_length=20,
            ),
        ),
    ]
