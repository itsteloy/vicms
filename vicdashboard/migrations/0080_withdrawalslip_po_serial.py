from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0079_waterweeklydenominationline'),
    ]

    operations = [
        migrations.AddField(
            model_name='withdrawalslip',
            name='po_number',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='withdrawalslipline',
            name='serial_number',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
