from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0020_joborder_format_update'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaterialBorrow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('borrow_number', models.CharField(max_length=50, unique=True)),
                ('date_borrowed', models.DateField()),
                ('borrower_name', models.CharField(max_length=200)),
                ('department', models.CharField(blank=True, default='', max_length=200)),
                ('purpose', models.TextField(blank=True, default='')),
                ('expected_return_date', models.DateField(blank=True, null=True)),
                ('remarks', models.TextField(blank=True, default='')),
                ('prepared_by', models.CharField(blank=True, default='', max_length=200)),
                ('noted_by', models.CharField(blank=True, default='', max_length=200)),
                ('approved_by', models.CharField(blank=True, default='', max_length=200)),
                ('status', models.CharField(choices=[('borrowed', 'Borrowed'), ('returned', 'Returned'), ('partial', 'Partially Returned'), ('overdue', 'Overdue')], default='borrowed', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-date_borrowed', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MaterialBorrowLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item_description', models.CharField(max_length=300)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('unit', models.CharField(blank=True, default='pcs', max_length=50)),
                ('remarks', models.CharField(blank=True, default='', max_length=200)),
                ('inventory_item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='borrow_lines', to='vicdashboard.inventoryitem')),
                ('material_borrow', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='vicdashboard.materialborrow')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
    ]
