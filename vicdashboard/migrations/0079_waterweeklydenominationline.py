from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0078_clear_otherpayment_amount_received'),
    ]

    operations = [
        migrations.CreateModel(
            name='WaterWeeklyDenominationLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('collection', models.CharField(choices=[('billing', 'Water Billing Collection'), ('refilling', 'Water Refilling Collection')], max_length=20)),
                ('denomination', models.PositiveIntegerField()),
                ('quantity', models.PositiveIntegerField(default=0)),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='denomination_lines', to='vicdashboard.waterweeklyreport')),
            ],
            options={
                'ordering': ['collection', '-denomination', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='waterweeklydenominationline',
            constraint=models.UniqueConstraint(fields=('report', 'collection', 'denomination'), name='uniq_water_weekly_denom_line'),
        ),
    ]
