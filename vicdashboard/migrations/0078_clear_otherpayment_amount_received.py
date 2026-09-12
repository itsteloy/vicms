from django.db import migrations


def clear_auto_amount_received(apps, schema_editor):
    """Reset auto-backfilled values so Amount total can include unpaid-received rows."""
    WaterOtherPayment = apps.get_model('vicdashboard', 'WaterOtherPayment')
    WaterOtherPayment.objects.all().update(amount_received=None)


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0077_waterotherpayment_amount_received'),
    ]

    operations = [
        migrations.RunPython(clear_auto_amount_received, migrations.RunPython.noop),
    ]
