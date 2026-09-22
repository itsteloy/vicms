from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0080_withdrawalslip_po_serial'),
    ]

    operations = [
        migrations.CreateModel(
            name='InventoryStockDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference_no', models.CharField(max_length=100)),
                ('date_arrived', models.DateField()),
                ('item_name', models.CharField(max_length=200)),
                ('quantity', models.PositiveIntegerField()),
                ('description', models.TextField(blank=True, default='')),
                ('supplier', models.CharField(blank=True, default='', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('inventory_item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_deliveries', to='vicdashboard.inventoryitem')),
            ],
            options={
                'ordering': ['-date_arrived', '-created_at'],
            },
        ),
    ]
