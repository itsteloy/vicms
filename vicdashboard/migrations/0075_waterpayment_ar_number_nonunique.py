from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0074_waterpayment_purpose_nullable_bill'),
    ]

    operations = [
        migrations.AlterField(
            model_name='waterpayment',
            name='ar_number',
            field=models.CharField(blank=True, db_index=True, max_length=50, null=True),
        ),
    ]
