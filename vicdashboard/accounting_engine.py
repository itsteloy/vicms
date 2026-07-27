"""Posting engine for the self-contained accounting module.

Nothing in here reads from or writes to SalesOrder / Quotation / ServiceQuotation /
RefundRecord / PayrollRun / Delivery. All transactions originate from the accounting
module's own models (Invoice, Bill, BankTransaction, PayrollExpenseEntry, or a manual
Journal Entry) and are posted here as balanced double-entry Journal Entries.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction as db_transaction

VAT_RATE = Decimal('12')
VAT_DIVISOR = Decimal('112')

# Chart of Accounts codes relied upon by auto-posting. Seeded by a data migration
# with is_system=True so they can never be deleted from under the posting engine.
ACCOUNT_CODES = {
    'cash_on_hand': '1000',
    'accounts_receivable': '1100',
    'inventory': '1200',
    'input_vat': '1500',
    'accounts_payable': '2000',
    'output_vat_payable': '2100',
    'withholding_tax_payable': '2200',
    'loans_payable': '2300',
    'owners_capital': '3000',
    'retained_earnings': '3100',
    'sales_revenue_product': '4000',
    'sales_revenue_service': '4100',
    'other_income': '4900',
    'cogs': '5000',
    'salaries_expense': '5100',
    'rent_expense': '5200',
    'utilities_expense': '5300',
    'office_supplies_expense': '5400',
    'misc_expense': '5500',
}


class UnbalancedEntryError(Exception):
    pass


def get_system_account(key):
    """Look up a seeded Chart of Accounts entry by its logical key (see ACCOUNT_CODES)."""
    from .models import Account
    code = ACCOUNT_CODES[key]
    return Account.objects.get(code=code)


def vat_components(gross_amount):
    """Split a VAT-inclusive gross amount into (net, vat) using the 12/112 factor."""
    gross = Decimal(gross_amount)
    vat = (gross * VAT_RATE / VAT_DIVISOR).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    net = gross - vat
    return net, vat


def generate_entry_number():
    from .models import JournalEntry
    year = date.today().year
    prefix = f'JE-{year}-'
    max_num = 0
    for number in JournalEntry.objects.filter(entry_number__startswith=prefix).values_list('entry_number', flat=True):
        suffix = number[len(prefix):]
        if suffix.isdigit():
            max_num = max(max_num, int(suffix))
    return f'{prefix}{max_num + 1:04d}'


@db_transaction.atomic
def post_journal_entry(entry_date, memo, source_type, lines, user=None, source_id=None):
    """Create a balanced JournalEntry + JournalEntryLine set.

    `lines` is a list of dicts: {'account': Account instance, 'debit': Decimal,
    'credit': Decimal, 'description': str (optional)}.
    Raises UnbalancedEntryError if the lines don't balance or are empty.
    """
    from .models import JournalEntry, JournalEntryLine

    clean_lines = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    for line in lines:
        debit = Decimal(line.get('debit') or 0)
        credit = Decimal(line.get('credit') or 0)
        if debit and credit:
            raise UnbalancedEntryError('A journal line cannot have both a debit and a credit.')
        if not debit and not credit:
            continue
        total_debit += debit
        total_credit += credit
        clean_lines.append({
            'account': line['account'],
            'debit': debit,
            'credit': credit,
            'description': line.get('description', ''),
        })

    if not clean_lines:
        raise UnbalancedEntryError('Journal entry has no lines.')
    if total_debit != total_credit:
        raise UnbalancedEntryError(
            f'Journal entry is not balanced (total debit={total_debit}, total credit={total_credit}).'
        )

    entry = JournalEntry.objects.create(
        entry_number=generate_entry_number(),
        entry_date=entry_date,
        memo=memo,
        source_type=source_type,
        source_id=source_id,
        created_by=user if (user is not None and getattr(user, 'is_authenticated', False)) else None,
    )
    JournalEntryLine.objects.bulk_create([
        JournalEntryLine(
            journal_entry=entry,
            account=line['account'],
            debit=line['debit'],
            credit=line['credit'],
            description=line['description'],
        )
        for line in clean_lines
    ])
    return entry


def void_journal_entry(entry, user=None, memo=None):
    """Reverse a posted entry with an equal-and-opposite entry, and flag the original void."""
    if entry.is_void:
        return None

    reversing_lines = [
        {
            'account': line.account,
            'debit': line.credit,
            'credit': line.debit,
            'description': f'Reversal: {line.description}'.strip(),
        }
        for line in entry.lines.all()
    ]
    reversal = post_journal_entry(
        entry_date=date.today(),
        memo=memo or f'Reversal of {entry.entry_number}',
        source_type='reversal',
        lines=reversing_lines,
        user=user,
        source_id=entry.id,
    )
    entry.is_void = True
    entry.save(update_fields=['is_void'])
    return reversal


# ---------------------------------------------------------------------------
# Transaction-specific posting helpers
# ---------------------------------------------------------------------------

def post_invoice(invoice, user=None):
    net, vat = vat_components(invoice.amount)
    entry = post_journal_entry(
        entry_date=invoice.invoice_date,
        memo=f'Invoice {invoice.invoice_number} – {invoice.customer.name}',
        source_type='invoice',
        source_id=invoice.id,
        user=user,
        lines=[
            {'account': get_system_account('accounts_receivable'), 'debit': invoice.amount,
             'description': f'AR – {invoice.customer.name}'},
            {'account': invoice.revenue_account, 'credit': net, 'description': 'Revenue (net of VAT)'},
            {'account': get_system_account('output_vat_payable'), 'credit': vat, 'description': 'Output VAT'},
        ],
    )
    invoice.vat_amount = vat
    invoice.related_journal_entry = entry
    invoice.refresh_status()
    invoice.save()
    return entry


def post_invoice_payment(payment, user=None):
    entry = post_journal_entry(
        entry_date=payment.payment_date,
        memo=f'Payment for {payment.invoice.invoice_number}',
        source_type='invoice_payment',
        source_id=payment.id,
        user=user,
        lines=[
            {'account': payment.bank_account.gl_account, 'debit': payment.amount,
             'description': f'Received into {payment.bank_account.name}'},
            {'account': get_system_account('accounts_receivable'), 'credit': payment.amount,
             'description': f'AR – {payment.invoice.customer.name}'},
        ],
    )
    payment.related_journal_entry = entry
    payment.save(update_fields=['related_journal_entry'])

    invoice = payment.invoice
    invoice.paid_amount = invoice.paid_amount + payment.amount
    invoice.refresh_status()
    invoice.save()
    return entry


def post_bill(bill, user=None):
    net, vat = vat_components(bill.amount)
    entry = post_journal_entry(
        entry_date=bill.bill_date,
        memo=f'Bill {bill.bill_number} – {bill.supplier.name}',
        source_type='bill',
        source_id=bill.id,
        user=user,
        lines=[
            {'account': bill.expense_account, 'debit': net, 'description': 'Expense (net of VAT)'},
            {'account': get_system_account('input_vat'), 'debit': vat, 'description': 'Input VAT'},
            {'account': get_system_account('accounts_payable'), 'credit': bill.amount,
             'description': f'AP – {bill.supplier.name}'},
        ],
    )
    bill.vat_amount = vat
    bill.related_journal_entry = entry
    bill.refresh_status()
    bill.save()
    return entry


def post_bill_payment(payment, user=None):
    entry = post_journal_entry(
        entry_date=payment.payment_date,
        memo=f'Payment for {payment.bill.bill_number}',
        source_type='bill_payment',
        source_id=payment.id,
        user=user,
        lines=[
            {'account': get_system_account('accounts_payable'), 'debit': payment.amount,
             'description': f'AP – {payment.bill.supplier.name}'},
            {'account': payment.bank_account.gl_account, 'credit': payment.amount,
             'description': f'Paid from {payment.bank_account.name}'},
        ],
    )
    payment.related_journal_entry = entry
    payment.save(update_fields=['related_journal_entry'])

    bill = payment.bill
    bill.paid_amount = bill.paid_amount + payment.amount
    bill.refresh_status()
    bill.save()
    return entry


def post_bank_transaction(txn, user=None):
    bank_line_account = txn.bank_account.gl_account
    lines = []
    if txn.transaction_type == 'deposit':
        lines = [
            {'account': bank_line_account, 'debit': txn.amount, 'description': txn.description or 'Deposit'},
            {'account': txn.contra_account, 'credit': txn.amount, 'description': txn.description or 'Deposit'},
        ]
    elif txn.transaction_type == 'withdrawal':
        lines = [
            {'account': txn.contra_account, 'debit': txn.amount, 'description': txn.description or 'Withdrawal'},
            {'account': bank_line_account, 'credit': txn.amount, 'description': txn.description or 'Withdrawal'},
        ]
    elif txn.transaction_type == 'transfer':
        lines = [
            {'account': txn.to_bank_account.gl_account, 'debit': txn.amount,
             'description': f'Transfer in from {txn.bank_account.name}'},
            {'account': bank_line_account, 'credit': txn.amount,
             'description': f'Transfer out to {txn.to_bank_account.name}'},
        ]

    entry = post_journal_entry(
        entry_date=txn.transaction_date,
        memo=f'{txn.get_transaction_type_display()} – {txn.bank_account.name}',
        source_type='bank_transaction',
        source_id=txn.id,
        user=user,
        lines=lines,
    )
    txn.related_journal_entry = entry
    txn.save(update_fields=['related_journal_entry'])
    return entry


def post_payroll_expense(entry_row, user=None):
    entry = post_journal_entry(
        entry_date=entry_row.entry_date,
        memo=entry_row.description or 'Payroll expense',
        source_type='payroll_expense',
        source_id=entry_row.id,
        user=user,
        lines=[
            {'account': entry_row.expense_account, 'debit': entry_row.amount, 'description': entry_row.description},
            {'account': entry_row.bank_account.gl_account, 'credit': entry_row.amount,
             'description': f'Paid from {entry_row.bank_account.name}'},
        ],
    )
    entry_row.related_journal_entry = entry
    entry_row.save(update_fields=['related_journal_entry'])
    return entry
