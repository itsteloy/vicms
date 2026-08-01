from django.db import migrations, models


def forwards_status(apps, schema_editor):
    WaterServiceAction = apps.get_model('vicdashboard', 'WaterServiceAction')
    WaterServiceAction.objects.filter(status='scheduled').update(status='for_disconnection')
    WaterServiceAction.objects.filter(status='completed').update(status='disconnected')
    WaterServiceAction.objects.filter(status='cancelled').update(status='for_disconnection')


def backwards_status(apps, schema_editor):
    WaterServiceAction = apps.get_model('vicdashboard', 'WaterServiceAction')
    WaterServiceAction.objects.filter(status='for_disconnection').update(status='scheduled')
    WaterServiceAction.objects.filter(status='disconnected').update(status='completed')


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0037_water_customer_first_last_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='watercustomer',
            name='connection_status',
            field=models.CharField(
                choices=[
                    ('active', 'Active'),
                    ('inactive', 'Inactive'),
                    ('for_disconnection', 'For disconnection'),
                    ('disconnected', 'Disconnected'),
                ],
                default='active',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='waterserviceaction',
            name='status',
            field=models.CharField(
                choices=[
                    ('for_disconnection', 'For disconnection'),
                    ('disconnected', 'Disconnected'),
                ],
                default='for_disconnection',
                max_length=20,
            ),
        ),
        migrations.RunPython(forwards_status, backwards_status),
    ]
