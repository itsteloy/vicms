from django.db import migrations, models


def migrate_job_order_fields(apps, schema_editor):
    JobOrder = apps.get_model('vicdashboard', 'JobOrder')
    for order in JobOrder.objects.order_by('pk'):
        updates = []
        if not order.names and getattr(order, 'customer_name', ''):
            order.names = order.customer_name
            updates.append('names')
        if not order.dates_covered and getattr(order, 'scheduled_date', None):
            order.dates_covered = order.scheduled_date.isoformat()
            updates.append('dates_covered')
        if updates:
            order.save(update_fields=updates)


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0019_seed_workspace_accounts'),
    ]

    operations = [
        migrations.RenameField(
            model_name='joborder',
            old_name='job_date',
            new_name='date_filed',
        ),
        migrations.RenameField(
            model_name='joborder',
            old_name='scope_of_work',
            new_name='job_description',
        ),
        migrations.RenameField(
            model_name='joborder',
            old_name='service_location',
            new_name='area_assignment',
        ),
        migrations.AddField(
            model_name='joborder',
            name='names',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='joborder',
            name='dates_covered',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='joborder',
            name='prepared_by',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='joborder',
            name='noted_by',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='joborder',
            name='approved_by',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AlterModelOptions(
            name='joborder',
            options={'ordering': ['-date_filed', '-created_at']},
        ),
        migrations.RunPython(migrate_job_order_fields, migrations.RunPython.noop),
        migrations.RemoveField(model_name='joborder', name='customer_name'),
        migrations.RemoveField(model_name='joborder', name='contact_person'),
        migrations.RemoveField(model_name='joborder', name='contact_number'),
        migrations.RemoveField(model_name='joborder', name='assigned_to'),
        migrations.RemoveField(model_name='joborder', name='scheduled_date'),
        migrations.RemoveField(model_name='joborder', name='priority'),
        migrations.RemoveField(model_name='joborder', name='notes'),
    ]
