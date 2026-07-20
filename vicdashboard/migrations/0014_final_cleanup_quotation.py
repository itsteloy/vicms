from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("vicdashboard", "0013_quotation_quotationline"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- Drop all known orphan columns that are NOT in the Quotation model
                ALTER TABLE vicdashboard_quotation DROP COLUMN IF EXISTS customer_name;
                ALTER TABLE vicdashboard_quotation DROP COLUMN IF EXISTS customer_title;
                ALTER TABLE vicdashboard_quotation DROP COLUMN IF EXISTS customer_contact_person;
                ALTER TABLE vicdashboard_quotation DROP COLUMN IF EXISTS status;
                ALTER TABLE vicdashboard_quotation DROP COLUMN IF EXISTS terms;
                ALTER TABLE vicdashboard_quotation DROP COLUMN IF EXISTS delivery_days;
                ALTER TABLE vicdashboard_quotation DROP COLUMN IF EXISTS validity_days;
                -- Add any other columns that appear in future errors here
            """,
            reverse_sql="""
                -- (Optional) Add them back if needed – not recommended
                ALTER TABLE vicdashboard_quotation ADD COLUMN customer_name varchar(200) NULL;
                ALTER TABLE vicdashboard_quotation ADD COLUMN customer_title varchar(200) NULL;
                ALTER TABLE vicdashboard_quotation ADD COLUMN customer_contact_person varchar(200) NULL;
                ALTER TABLE vicdashboard_quotation ADD COLUMN status varchar(20) NULL;
                ALTER TABLE vicdashboard_quotation ADD COLUMN terms text NULL;
                ALTER TABLE vicdashboard_quotation ADD COLUMN delivery_days integer NULL;
                ALTER TABLE vicdashboard_quotation ADD COLUMN validity_days integer NULL;
            """,
        ),
    ]
