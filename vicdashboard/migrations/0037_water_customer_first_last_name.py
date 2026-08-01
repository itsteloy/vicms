from django.db import migrations, models


def split_full_names(apps, schema_editor):
    WaterCustomer = apps.get_model('vicdashboard', 'WaterCustomer')
    for customer in WaterCustomer.objects.all():
        full = (getattr(customer, 'full_name', '') or '').strip()
        parts = full.split()
        if not parts:
            customer.first_name = ''
            customer.last_name = ''
        elif len(parts) == 1:
            customer.first_name = parts[0].upper()
            customer.last_name = ''
        else:
            customer.last_name = parts[-1].upper()
            customer.first_name = ' '.join(parts[:-1]).upper()
        customer.save(update_fields=['first_name', 'last_name'])


def combine_names(apps, schema_editor):
    WaterCustomer = apps.get_model('vicdashboard', 'WaterCustomer')
    for customer in WaterCustomer.objects.all():
        first = (customer.first_name or '').strip()
        last = (customer.last_name or '').strip()
        customer.full_name = f'{first} {last}'.strip().upper()
        customer.save(update_fields=['full_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0036_water_payment_methods_cash_gcash'),
    ]

    operations = [
        migrations.AddField(
            model_name='watercustomer',
            name='first_name',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='watercustomer',
            name='last_name',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
        migrations.RunPython(split_full_names, combine_names),
        migrations.RemoveField(
            model_name='watercustomer',
            name='full_name',
        ),
    ]
