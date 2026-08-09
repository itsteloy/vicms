from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Q

from .models import DeductionConfig, EmployeeDeduction, TaxBracket

# DeductionConfig codes shown as dedicated payroll columns.
PAYROLL_DEDUCTION_CODES = {
    'PHILHEALTH': 'philhealth',
    'SSS': 'sss',
    'HDMF': 'hdmf',
    'SSS_LOAN': 'sss_loan',
    'HDMF_LOAN': 'hdmf_loan',
}

# Older installs may still have SS_LOAN in the DB.
DEDUCTION_CODE_ALIASES = {
    'SS_LOAN': 'SSS_LOAN',
}


def _normalize_deduction_code(code: str | None) -> str:
    value = (code or '').upper()
    return DEDUCTION_CODE_ALIASES.get(value, value)


# TaxBracket.tax_type used when DeductionConfig has no amount and no employee assignment.
TAX_BRACKET_BY_CODE = {
    'PHILHEALTH': 'philhealth',
    'SSS': 'sss',
    'HDMF': 'pagibig',
}

ZERO = Decimal('0.00')


def get_effective_shift_schedule(employee, date):
    shifts = employee.shift_schedules.filter(
        effective_date__lte=date,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=date)
    ).order_by('-effective_date')
    return shifts.first()


def get_attendance_for_period(employee, start_date, end_date):
    return employee.attendance_logs.filter(
        date__gte=start_date,
        date__lte=end_date,
    ).order_by('date')


def compute_daily_hours(log, shift):
    if not log.clock_in or not log.clock_out:
        return Decimal('0'), Decimal('0')

    start = datetime.combine(log.date, log.clock_in)
    end = datetime.combine(log.date, log.clock_out)
    if end < start:
        end += timedelta(days=1)

    total_hours = Decimal(str((end - start).total_seconds() / 3600))

    if log.break_start and log.break_end:
        break_start = datetime.combine(log.date, log.break_start)
        break_end = datetime.combine(log.date, log.break_end)
        if break_end < break_start:
            break_end += timedelta(days=1)
        break_hours = Decimal(str((break_end - break_start).total_seconds() / 3600))
    else:
        break_hours = Decimal('0')

    worked_hours = total_hours - break_hours

    shift_start = datetime.combine(log.date, shift.start_time)
    shift_end = datetime.combine(log.date, shift.end_time)
    if shift_end < shift_start:
        shift_end += timedelta(days=1)
    shift_hours = Decimal(str((shift_end - shift_start).total_seconds() / 3600))

    regular_hours = min(worked_hours, shift_hours)
    overtime_hours = max(worked_hours - shift_hours, Decimal('0'))
    return regular_hours, overtime_hours


def get_tax(employee, gross_pay, cutoff_date):
    brackets = TaxBracket.objects.filter(
        tax_type='withholding',
        effective_date__lte=cutoff_date,
    ).order_by('effective_date', 'min_amount')
    if not brackets.exists():
        return Decimal('0')

    taxable = gross_pay
    for bracket in brackets:
        if bracket.max_amount is not None and taxable > bracket.max_amount:
            continue
        if taxable >= bracket.min_amount:
            excess = taxable - bracket.min_amount
            return bracket.base_tax + (excess * bracket.tax_rate)
    latest = brackets.last()
    return taxable * latest.tax_rate


def get_statutory_deductions(employee, gross_pay, cutoff_date):
    total = Decimal('0')
    for tax_type in ('sss', 'philhealth', 'pagibig'):
        total += _tax_bracket_amount(tax_type, gross_pay, cutoff_date)
    return total


def _tax_bracket_amount(tax_type, gross_pay, cutoff_date):
    bracket = TaxBracket.objects.filter(
        tax_type=tax_type,
        effective_date__lte=cutoff_date,
    ).order_by('-effective_date').first()
    if not bracket:
        return ZERO
    amount = (gross_pay * bracket.tax_rate).quantize(Decimal('0.01'))
    # Pag-IBIG employee share is commonly capped at ₱100 per month.
    if tax_type == 'pagibig':
        amount = min(amount, Decimal('100.00'))
    return amount


def get_voluntary_deductions(employee, cutoff_start, cutoff_end):
    """Sum of active EmployeeDeduction amounts for the cutoff (legacy total)."""
    return get_payroll_deductions(
        employee,
        gross_pay=ZERO,
        cutoff_start=cutoff_start,
        cutoff_end=cutoff_end,
    )['total']


def _money(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def get_payroll_deductions(
    employee,
    gross_pay,
    cutoff_start,
    cutoff_end,
    *,
    include_config_defaults=False,
    include_tax_brackets=False,
):
    """
    Resolve PhilHealth / SSS / HDMF / SSS Loan / HDMF Loan (and other assigned deductions).

    By default only **EmployeeDeduction** assignments for the cutoff apply.
    Nothing is deducted until HR assigns a deduction on the Deductions tab.

    Optional (off by default):
    - include_config_defaults: use active DeductionConfig fixed/% when not assigned
    - include_tax_brackets: fall back to TaxBracket rates for statutory codes
    """
    gross_pay = _money(gross_pay)
    result = {
        'philhealth': ZERO,
        'sss': ZERO,
        'hdmf': ZERO,
        'sss_loan': ZERO,
        'hdmf_loan': ZERO,
        'other': ZERO,
        'statutory': ZERO,
        'voluntary': ZERO,
        'total': ZERO,
        'items': {},
    }

    assignments = list(
        EmployeeDeduction.objects.filter(
            employee=employee,
            start_date__lte=cutoff_end,
        )
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=cutoff_start))
        .select_related('deduction_config')
    )

    assigned_by_code = {}
    for ded in assignments:
        code = _normalize_deduction_code(ded.deduction_config.code)
        assigned_by_code.setdefault(code, ZERO)
        assigned_by_code[code] += _money(ded.amount)

    configs = {
        _normalize_deduction_code(c.code): c
        for c in DeductionConfig.objects.filter(is_active=True)
    } if include_config_defaults else {}

    handled_codes = set()
    for code, key in PAYROLL_DEDUCTION_CODES.items():
        amount = ZERO
        source = None
        if code in assigned_by_code:
            amount = assigned_by_code[code]
            source = 'assignment'
        elif include_config_defaults and code in configs:
            cfg = configs[code]
            effective = cfg.effective_date <= cutoff_end
            ended = cfg.end_date is not None and cfg.end_date < cutoff_start
            if effective and not ended:
                fixed = _money(cfg.fixed_amount)
                pct = Decimal(str(cfg.percentage_of_gross or 0))
                from_pct = (gross_pay * pct / Decimal('100')).quantize(Decimal('0.01')) if pct else ZERO
                amount = fixed + from_pct
                if amount > 0:
                    source = 'config'
        if amount == ZERO and include_tax_brackets and code in TAX_BRACKET_BY_CODE:
            amount = _tax_bracket_amount(
                TAX_BRACKET_BY_CODE[code],
                gross_pay,
                cutoff_end,
            )
            if amount > 0:
                source = 'tax_bracket'

        result[key] = amount
        handled_codes.add(code)
        if amount > 0 or source:
            result['items'][key] = {
                'code': code,
                'amount': float(amount),
                'source': source,
            }

    other = ZERO
    for code, amount in assigned_by_code.items():
        if code in handled_codes:
            continue
        other += amount
    result['other'] = other
    if other > 0:
        result['items']['other'] = {'code': 'OTHER', 'amount': float(other), 'source': 'assignment'}

    result['statutory'] = result['philhealth'] + result['sss'] + result['hdmf']
    # Loan + misc assigned deductions (excludes statutory configs).
    result['voluntary'] = result['sss_loan'] + result['hdmf_loan'] + result['other']
    result['total'] = result['statutory'] + result['voluntary']
    return result
