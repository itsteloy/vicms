from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0081_inventorystockdelivery'),
    ]

    operations = [
        migrations.AlterField(
            model_name='waterweeklyreport',
            name='prepared_by',
            field=models.CharField(blank=True, default='AIZA MAE POQUITA', max_length=200),
        ),
        migrations.AlterField(
            model_name='waterweeklyreport',
            name='audited_by',
            field=models.CharField(blank=True, default='CHRISTINE JOY ILOGON', max_length=200),
        ),
        migrations.AlterField(
            model_name='waterweeklyreport',
            name='approved_by',
            field=models.CharField(blank=True, default='ENGR. ARTURO I. DAVIS, PME, PhD', max_length=200),
        ),
    ]
