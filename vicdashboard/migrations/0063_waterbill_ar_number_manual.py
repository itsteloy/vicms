from django.db import migrations, models


def empty_ar_to_null(apps, schema_editor):
    WaterBill = apps.get_model('vicdashboard', 'WaterBill')
    WaterBill.objects.filter(ar_number='').update(ar_number=None)


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0062_waterbill_ar_number'),
    ]

    operations = [
        migrations.RunPython(empty_ar_to_null, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='waterbill',
            name='ar_number',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
    ]
