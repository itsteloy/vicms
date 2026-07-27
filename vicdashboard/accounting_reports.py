"""On-the-fly financial reports computed from JournalEntry / JournalEntryLine.

Nothing here is persisted — every report is derived live from the ledger so it is
always consistent with whatever has been posted.
"""
from decimal import Decimal

from django.db.models import Sum

from .accounting_engine import get_system_account


def _activity(account, start_date=None, end_date=None):
    from .models import JournalEntryLine
    qs = JournalEntryLine.objects.filter(account=account)
    if start_date:
        qs = qs.filter(journal_entry__entry_date__gte=start_date)
    if end_date:
        qs = qs.filter(journal_entry__entry_date__lte=end_date)
    agg = qs.aggregate(d=Sum('debit'), c=Sum('credit'))
    return agg['d'] or Decimal('0'), agg['c'] or Decimal('0')


def trial_balance(as_of_date=None):
    from .models import Account
    rows = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    for account in Account.objects.filter(is_active=True).order_by('code'):
        debit, credit = _activity(account, end_date=as_of_date)
        if account.normal_balance == 'debit':
            balance = debit - credit
            debit_col, credit_col = (balance, Decimal('0')) if balance >= 0 else (Decimal('0'), -balance)
        else:
            balance = credit - debit
            debit_col, credit_col = (Decimal('0'), balance) if balance >= 0 else (-balance, Decimal('0'))
        if debit_col or credit_col:
            rows.append({'account': account, 'debit': debit_col, 'credit': credit_col})
            total_debit += debit_col
            total_credit += credit_col
    return {'rows': rows, 'total_debit': total_debit, 'total_credit': total_credit}


def general_ledger(account, start_date=None, end_date=None):
    from .models import JournalEntryLine
    qs = JournalEntryLine.objects.filter(account=account).select_related('journal_entry').order_by(
        'journal_entry__entry_date', 'journal_entry__created_at', 'id'
    )
    if start_date:
        qs = qs.filter(journal_entry__entry_date__gte=start_date)
    if end_date:
        qs = qs.filter(journal_entry__entry_date__lte=end_date)

    running = Decimal('0')
    rows = []
    for line in qs:
        if account.normal_balance == 'debit':
            running += line.debit - line.credit
        else:
            running += line.credit - line.debit
        rows.append({'line': line, 'running_balance': running})
    return rows


def income_statement(start_date, end_date):
    from .models import Account
    revenue_rows, expense_rows = [], []
    for account in Account.objects.filter(account_type='revenue', is_active=True).order_by('code'):
        debit, credit = _activity(account, start_date, end_date)
        amount = credit - debit
        if amount:
            revenue_rows.append({'account': account, 'amount': amount})
    for account in Account.objects.filter(account_type='expense', is_active=True).order_by('code'):
        debit, credit = _activity(account, start_date, end_date)
        amount = debit - credit
        if amount:
            expense_rows.append({'account': account, 'amount': amount})

    total_revenue = sum((r['amount'] for r in revenue_rows), Decimal('0'))
    total_expense = sum((r['amount'] for r in expense_rows), Decimal('0'))
    return {
        'revenue_rows': revenue_rows,
        'expense_rows': expense_rows,
        'total_revenue': total_revenue,
        'total_expense': total_expense,
        'net_income': total_revenue - total_expense,
    }


def balance_sheet(as_of_date):
    from .models import Account
    from datetime import date as date_cls

    asset_rows, liability_rows, equity_rows = [], [], []
    for account in Account.objects.filter(account_type='asset', is_active=True).order_by('code'):
        debit, credit = _activity(account, end_date=as_of_date)
        balance = debit - credit
        if balance:
            asset_rows.append({'account': account, 'amount': balance})
    for account in Account.objects.filter(account_type='liability', is_active=True).order_by('code'):
        debit, credit = _activity(account, end_date=as_of_date)
        balance = credit - debit
        if balance:
            liability_rows.append({'account': account, 'amount': balance})
    for account in Account.objects.filter(account_type='equity', is_active=True).order_by('code'):
        debit, credit = _activity(account, end_date=as_of_date)
        balance = credit - debit
        if balance:
            equity_rows.append({'account': account, 'amount': balance})

    total_assets = sum((r['amount'] for r in asset_rows), Decimal('0'))
    total_liabilities = sum((r['amount'] for r in liability_rows), Decimal('0'))
    equity_from_accounts = sum((r['amount'] for r in equity_rows), Decimal('0'))

    inception_income = income_statement(date_cls(2000, 1, 1), as_of_date)
    cumulative_net_income = inception_income['net_income']

    total_equity = equity_from_accounts + cumulative_net_income
    return {
        'asset_rows': asset_rows,
        'liability_rows': liability_rows,
        'equity_rows': equity_rows,
        'cumulative_net_income': cumulative_net_income,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_equity': total_equity,
        'total_liabilities_and_equity': total_liabilities + total_equity,
    }


def cash_flow_statement(start_date, end_date):
    from .models import JournalEntryLine

    cash_lines = (
        JournalEntryLine.objects.filter(
            account__category__in=['cash', 'bank'],
            journal_entry__entry_date__gte=start_date,
            journal_entry__entry_date__lte=end_date,
        )
        .select_related('journal_entry', 'account')
        .prefetch_related('journal_entry__lines__account')
    )

    operating = investing = financing = Decimal('0')
    for cash_line in cash_lines:
        net = cash_line.debit - cash_line.credit
        other_lines = [
            l for l in cash_line.journal_entry.lines.all()
            if l.id != cash_line.id and l.account.category not in ('cash', 'bank')
        ]
        category = 'operating'
        if other_lines:
            contra_category = other_lines[0].account.category
            if contra_category == 'fixed_asset':
                category = 'investing'
            elif contra_category in ('loan_payable', 'equity'):
                category = 'financing'
        if category == 'operating':
            operating += net
        elif category == 'investing':
            investing += net
        else:
            financing += net

    return {
        'operating': operating,
        'investing': investing,
        'financing': financing,
        'net_change': operating + investing + financing,
    }


def vat_summary(start_date, end_date):
    output_account = get_system_account('output_vat_payable')
    input_account = get_system_account('input_vat')
    out_debit, out_credit = _activity(output_account, start_date, end_date)
    in_debit, in_credit = _activity(input_account, start_date, end_date)
    output_vat = out_credit - out_debit
    input_vat = in_debit - in_credit
    return {
        'output_vat': output_vat,
        'input_vat': input_vat,
        'net_vat_payable': output_vat - input_vat,
    }
