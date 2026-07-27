from datetime import date

from django.db import migrations


# Standard PH-SME Chart of Accounts. All rows are is_system=True so the posting
# engine (vicdashboard/accounting_engine.py) always has a target account and these
# rows can never be deleted through the UI.
CHART_OF_ACCOUNTS = [
    # code, name, account_type, category
    ('1000', 'Cash on Hand', 'asset', 'cash'),
    ('1010', 'Bank – Primary Account', 'asset', 'bank'),
    ('1100', 'Accounts Receivable', 'asset', 'ar'),
    ('1200', 'Inventory', 'asset', 'inventory'),
    ('1500', 'Input VAT (Creditable)', 'asset', 'tax_input'),
    ('2000', 'Accounts Payable', 'liability', 'ap'),
    ('2100', 'Output VAT Payable', 'liability', 'tax_output'),
    ('2200', 'Withholding Tax Payable', 'liability', 'tax_payable'),
    ('2300', 'Loans Payable', 'liability', 'loan_payable'),
    ('3000', "Owner's Capital", 'equity', 'equity'),
    ('3100', 'Retained Earnings', 'equity', 'equity'),
    ('4000', 'Sales Revenue – Product', 'revenue', 'revenue'),
    ('4100', 'Sales Revenue – Service', 'revenue', 'revenue'),
    ('4900', 'Other Income', 'revenue', 'revenue'),
    ('5000', 'Cost of Goods Sold', 'expense', 'cogs'),
    ('5100', 'Salaries Expense', 'expense', 'operating_expense'),
    ('5200', 'Rent Expense', 'expense', 'operating_expense'),
    ('5300', 'Utilities Expense', 'expense', 'operating_expense'),
    ('5400', 'Office Supplies Expense', 'expense', 'operating_expense'),
    ('5500', 'Miscellaneous Expense', 'expense', 'operating_expense'),
]


def seed_chart_of_accounts(apps, schema_editor):
    Account = apps.get_model('vicdashboard', 'Account')
    for code, name, account_type, category in CHART_OF_ACCOUNTS:
        Account.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'account_type': account_type,
                'category': category,
                'is_system': True,
                'is_active': True,
            },
        )


def unseed_chart_of_accounts(apps, schema_editor):
    Account = apps.get_model('vicdashboard', 'Account')
    codes = [row[0] for row in CHART_OF_ACCOUNTS]
    Account.objects.filter(code__in=codes, is_system=True).delete()


def seed_tax_deadlines(apps, schema_editor):
    TaxDeadline = apps.get_model('vicdashboard', 'TaxDeadline')

    def add_days(d, days):
        from datetime import timedelta
        return d + timedelta(days=days)

    def add_deadline(name, tax_type, period_start, period_end, due_date):
        TaxDeadline.objects.get_or_create(
            name=name,
            tax_type=tax_type,
            period_start=period_start,
            period_end=period_end,
            defaults={'due_date': due_date},
        )

    # ---- VAT (BIR Form 2550Q) — quarterly, due 25 days after quarter close ----
    vat_quarters = [
        (date(2026, 7, 1), date(2026, 9, 30), date(2026, 10, 25)),
        (date(2026, 10, 1), date(2026, 12, 31), date(2027, 1, 25)),
        (date(2027, 1, 1), date(2027, 3, 31), date(2027, 4, 25)),
        (date(2027, 4, 1), date(2027, 6, 30), date(2027, 7, 25)),
    ]
    for start, end, due in vat_quarters:
        add_deadline(f'VAT 2550Q – Q{((start.month - 1) // 3) + 1} {start.year}', 'vat', start, end, due)

    # ---- Withholding Tax on Compensation (BIR Form 1601-C) — monthly, due the ----
    # ---- 10th of the following month (Dec. withheld tax is due Jan. 15) ----
    months = [
        (2026, 7), (2026, 8), (2026, 9), (2026, 10), (2026, 11), (2026, 12),
        (2027, 1), (2027, 2), (2027, 3), (2027, 4), (2027, 5), (2027, 6),
    ]
    for year, month in months:
        period_start = date(year, month, 1)
        if month == 12:
            period_end = date(year, 12, 31)
            due = date(year + 1, 1, 15)
        else:
            next_month = date(year, month + 1, 1)
            period_end = add_days(next_month, -1)
            due = date(year, month + 1, 10)
        add_deadline(
            f'Withholding Tax on Compensation 1601-C – {period_start.strftime("%B %Y")}',
            'withholding_compensation', period_start, period_end, due,
        )

    # ---- Quarterly Income Tax (1701Q/1702Q) — due 60 days after quarter close ----
    quarterly_income_tax = [
        (date(2026, 4, 1), date(2026, 6, 30), date(2026, 8, 29)),
        (date(2026, 7, 1), date(2026, 9, 30), date(2026, 11, 29)),
        (date(2027, 1, 1), date(2027, 3, 31), date(2027, 5, 30)),
    ]
    for start, end, due in quarterly_income_tax:
        add_deadline(
            f'Quarterly Income Tax – Q{((start.month - 1) // 3) + 1} {start.year}',
            'income_tax_quarterly', start, end, due,
        )

    # ---- Annual Income Tax — due April 15 of the following year ----
    add_deadline(
        'Annual Income Tax – FY 2026', 'income_tax_annual',
        date(2026, 1, 1), date(2026, 12, 31), date(2027, 4, 15),
    )


def unseed_tax_deadlines(apps, schema_editor):
    TaxDeadline = apps.get_model('vicdashboard', 'TaxDeadline')
    TaxDeadline.objects.filter(
        period_start__gte=date(2026, 1, 1), period_end__lte=date(2027, 12, 31),
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0024_accounting_core'),
    ]

    operations = [
        migrations.RunPython(seed_chart_of_accounts, unseed_chart_of_accounts),
        migrations.RunPython(seed_tax_deadlines, unseed_tax_deadlines),
    ]
