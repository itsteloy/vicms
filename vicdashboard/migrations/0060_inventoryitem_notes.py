from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0059_water_allow_negative_consumption'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryitem',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
    ]
