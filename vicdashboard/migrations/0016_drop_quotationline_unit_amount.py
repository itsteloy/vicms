from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("vicdashboard", "0015_final_fix_quotationline"),  # last migration you applied
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE vicdashboard_quotationline DROP COLUMN IF EXISTS unit_amount;
                -- If other columns appear, add them here:
                -- ALTER TABLE vicdashboard_quotationline DROP COLUMN IF EXISTS total_price;
                -- ALTER TABLE vicdashboard_quotationline DROP COLUMN IF EXISTS line_total;
            """,
            reverse_sql="""
                ALTER TABLE vicdashboard_quotationline ADD COLUMN unit_amount numeric(14,2) NULL;
            """,
        ),
    ]
