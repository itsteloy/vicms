# Clear employee records before schema rename

from django.db import migrations


def clear_employee_data(apps, schema_editor):
    Employee = apps.get_model('vicdashboard', 'Employee')
    Department = apps.get_model('vicdashboard', 'Department')
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names())
        if 'vicdashboard_joborder_assignees' in tables:
            cursor.execute('DELETE FROM vicdashboard_joborder_assignees')
    Employee.objects.all().delete()
    Department.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0045_payperiod_semimonthly_default'),
    ]

    operations = [
        migrations.RunPython(clear_employee_data, migrations.RunPython.noop),
    ]
