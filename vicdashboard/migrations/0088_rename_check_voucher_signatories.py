# The 0086 migration file was renamed (prepared_by/checked_by_1/checked_by_2/
# approved_by -> signatory_prepared/signatory_checked/signatory_approved/
# signatory_approver) after it had already been applied, so the database still
# carries the old column names. Bring the database in line with migration state.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0087_check_voucher_check_date_archive_type'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE vicdashboard_checkvoucher RENAME COLUMN prepared_by TO signatory_prepared;',
                    reverse_sql='ALTER TABLE vicdashboard_checkvoucher RENAME COLUMN signatory_prepared TO prepared_by;',
                ),
                migrations.RunSQL(
                    sql='ALTER TABLE vicdashboard_checkvoucher RENAME COLUMN checked_by_1 TO signatory_checked;',
                    reverse_sql='ALTER TABLE vicdashboard_checkvoucher RENAME COLUMN signatory_checked TO checked_by_1;',
                ),
                migrations.RunSQL(
                    sql='ALTER TABLE vicdashboard_checkvoucher RENAME COLUMN checked_by_2 TO signatory_approved;',
                    reverse_sql='ALTER TABLE vicdashboard_checkvoucher RENAME COLUMN signatory_approved TO checked_by_2;',
                ),
                migrations.RunSQL(
                    sql='ALTER TABLE vicdashboard_checkvoucher RENAME COLUMN approved_by TO signatory_approver;',
                    reverse_sql='ALTER TABLE vicdashboard_checkvoucher RENAME COLUMN signatory_approver TO approved_by;',
                ),
            ],
            state_operations=[],
        ),
    ]
