from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0075_waterpayment_ar_number_nonunique'),
    ]

    operations = [
        migrations.CreateModel(
            name='WaterOtherPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_date', models.DateField()),
                ('ar_number', models.CharField(blank=True, db_index=True, max_length=50, null=True)),
                ('received_from', models.CharField(max_length=200)),
                ('address', models.CharField(blank=True, default='', max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('payment_of', models.CharField(help_text='What the payment is for', max_length=255)),
                ('remarks', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-payment_date', '-created_at'],
            },
        ),
    ]
