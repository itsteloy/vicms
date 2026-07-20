from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        (
            "vicdashboard",
            "0014_final_cleanup_quotation",
        ),  # make sure this is the last one
    ]

    operations = [
        # 1. Remove the unwanted unique constraint on quotation_number
        migrations.RunSQL(
            sql="""
                ALTER TABLE vicdashboard_quotation DROP CONSTRAINT IF EXISTS vicdashboard_quotation_quotation_number_key;
            """,
            reverse_sql="""
                ALTER TABLE vicdashboard_quotation ADD CONSTRAINT vicdashboard_quotation_quotation_number_key UNIQUE (quotation_number);
            """,
        ),
        # 2. Add missing columns to quotationline if they don't exist
        migrations.RunSQL(
            sql="""
                -- Ensure all columns from the QuotationLine model exist
                ALTER TABLE vicdashboard_quotationline ADD COLUMN IF NOT EXISTS item_number integer NOT NULL DEFAULT 0;
                ALTER TABLE vicdashboard_quotationline ADD COLUMN IF NOT EXISTS product_description text NOT NULL DEFAULT '';
                ALTER TABLE vicdashboard_quotationline ADD COLUMN IF NOT EXISTS quantity integer NOT NULL DEFAULT 0;
                ALTER TABLE vicdashboard_quotationline ADD COLUMN IF NOT EXISTS unit varchar(50) NOT NULL DEFAULT '';
                ALTER TABLE vicdashboard_quotationline ADD COLUMN IF NOT EXISTS unit_price numeric(14,2) NOT NULL DEFAULT 0;
                ALTER TABLE vicdashboard_quotationline ADD COLUMN IF NOT EXISTS total_amount numeric(14,2) NOT NULL DEFAULT 0;
            """,
            reverse_sql="""
                -- (Optional) revert changes
            """,
        ),
    ]
