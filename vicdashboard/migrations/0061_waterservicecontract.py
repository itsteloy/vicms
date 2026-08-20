# Generated manually for WaterServiceContract

from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0060_inventoryitem_notes'),
    ]

    operations = [
        migrations.CreateModel(
            name='WaterServiceContract',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('application_status', models.CharField(choices=[('new', 'New'), ('reconnection', 'Reconnection'), ('transfer', 'Transfer / Change name')], default='new', max_length=20)),
                ('last_name', models.CharField(blank=True, default='', max_length=100)),
                ('first_name', models.CharField(blank=True, default='', max_length=100)),
                ('middle_name', models.CharField(blank=True, default='', max_length=100)),
                ('zone_purok', models.CharField(blank=True, default='', max_length=200)),
                ('barangay', models.CharField(blank=True, default='', max_length=200)),
                ('municipality_city', models.CharField(blank=True, default='', max_length=200)),
                ('contact_number', models.CharField(blank=True, default='', max_length=50)),
                ('spouse_last_name', models.CharField(blank=True, default='', max_length=100)),
                ('spouse_first_name', models.CharField(blank=True, default='', max_length=100)),
                ('spouse_middle_name', models.CharField(blank=True, default='', max_length=100)),
                ('home_ownership', models.CharField(blank=True, choices=[('owner', 'Owner'), ('rented', 'Rented'), ('contractor', 'Contractor')], default='', max_length=20)),
                ('customer_classification', models.CharField(blank=True, choices=[('residential', 'Residential'), ('government', 'Government / Institutional'), ('commercial', 'Commercial / Industrial')], default='', max_length=20)),
                ('original_registered_name', models.CharField(blank=True, default='', max_length=200)),
                ('meter_size', models.CharField(blank=True, default='', max_length=50)),
                ('connection_location', models.TextField(blank=True, default='')),
                ('near_beside', models.CharField(blank=True, default='', max_length=200)),
                ('ack_payee_name', models.CharField(blank=True, default='', max_length=200)),
                ('ack_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14)),
                ('ack_received_by', models.CharField(blank=True, default='', max_length=200)),
                ('ack_date', models.DateField(blank=True, null=True)),
                ('contract_date', models.DateField(blank=True, null=True)),
                ('civil_status', models.CharField(blank=True, choices=[('single', 'Single'), ('married', 'Married')], default='', max_length=20)),
                ('contract_spouse_name', models.CharField(blank=True, default='', max_length=200)),
                ('contract_address', models.TextField(blank=True, default='')),
                ('signed_day', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('signed_month', models.CharField(blank=True, default='', max_length=20)),
                ('signed_year', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('notary_province', models.CharField(blank=True, default='', max_length=100)),
                ('notary_city', models.CharField(blank=True, default='', max_length=100)),
                ('notary_day', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('notary_month', models.CharField(blank=True, default='', max_length=20)),
                ('notary_year', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('notary_location', models.CharField(blank=True, default='', max_length=200)),
                ('notary_witness1_name', models.CharField(blank=True, default='', max_length=200)),
                ('notary_witness1_id', models.CharField(blank=True, default='', max_length=100)),
                ('notary_witness1_id_issued', models.CharField(blank=True, default='', max_length=100)),
                ('notary_witness1_id_at', models.CharField(blank=True, default='', max_length=200)),
                ('notary_witness2_name', models.CharField(blank=True, default='', max_length=200)),
                ('notary_witness2_id', models.CharField(blank=True, default='', max_length=100)),
                ('notary_witness2_id_issued', models.CharField(blank=True, default='', max_length=100)),
                ('notary_witness2_id_at', models.CharField(blank=True, default='', max_length=200)),
                ('notary_doc_no', models.CharField(blank=True, default='', max_length=50)),
                ('notary_page_no', models.CharField(blank=True, default='', max_length=50)),
                ('notary_book_no', models.CharField(blank=True, default='', max_length=50)),
                ('notary_series_year', models.CharField(blank=True, default='', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='service_contracts', to='vicdashboard.watercustomer')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
