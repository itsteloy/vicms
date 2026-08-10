"""Payroll register data: shared serializer for PDF and Excel exports."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .models import (
    Employee,
    Holiday,
    LeaveBalance,
    PayrollLine,
    PayrollRun,
    estimated_daily_rate,
    idle_calendar_days,
)
from .payroll_calculator import compute_daily_hours, get_attendance_for_period, get_effective_shift_schedule

ZERO = Decimal('0.00')
OT_REG_FACTOR = Decimal('1.25')
# Rest-day / special non-working premium (+30%) used by the company register sheet.
OT_SUN_FACTOR = Decimal('1.30')
SNWD_FACTOR = Decimal('1.30')
SNW_SUNDAY_FACTOR = Decimal('1.30')
REGULAR_HOLIDAY_FACTOR = Decimal('1.00')

REGISTER_SIGNATURES = [
    {
        'label': 'PREPARED BY',
        'name': 'ANGELMARIE M. DAPAR',
        'title': '',
    },
    {
        'label': 'CHECKED BY',
        'name': 'CHRISTINE JOY C. ILOGON',
        'title': 'EXECUTIVE ASSISTANT',
    },
    {
        'label': 'RECOMMENDING APPROVAL',
        'name': 'RINO M. TUGAY',
        'title': 'HR HEAD - MRT MANPOWER',
    },
    {
        'label': 'APPROVED BY',
        'name': 'ENGR. ARTURO J. DAVIS, PME',
        'title': 'PRESIDENT/GEN. MANAGER',
    },
]

# Leaf columns in left-to-right order (matches the sample spreadsheet).
LEAF_COLUMNS = [
    ('no', 'NO.'),
    ('name', 'NAME'),
    ('sil_on_hand', 'SIL ON HAND'),
    ('daily_rate', 'DAILY RATE'),
    ('hourly_rate', 'HRLY RATE'),
    ('reg_days', 'DAYS'),
    ('lwp_days', 'LWP'),
    ('total_days', 'TOTAL DAYS'),
    ('reg_total', 'TOTAL'),
    ('ot_reg_hours', 'REG'),
    ('ot_reg_amount', 'AMOUNT'),
    ('ot_sun_hours', 'SUN/RD'),
    ('ot_sun_amount', 'AMOUNT'),
    ('ot_total_hours', 'TOTAL O.T (HRS)'),
    ('ot_total_amount', 'TOTAL AMOUNT'),
    ('snwd_days', 'DAYS'),
    ('snwd_amount', 'AMOUNT'),
    ('snw_sun_days', 'DAYS'),
    ('snw_sun_amount', 'AMOUNT'),
    ('rh_days', 'DAYS'),
    ('rh_amount', 'AMOUNT'),
    ('gross_pay', 'GROSS PAY'),
    ('philhealth', 'PHIL CONTRI'),
    ('sss', 'SSS CONTRI'),
    ('hdmf', 'HDMF CONTRI'),
    ('hdmf_loan', 'HDMF LOAN'),
    ('sss_loan', 'SSS LOAN'),
    ('late_ut_mins', 'LATE/UT (MINS)'),
    ('late_ut_amount', 'LATE/UT (-)'),
    ('total_deductions', 'TOTAL (-)'),
    ('net_pay', 'NET PAY'),
]

# Group header row: (label, start_leaf_key, span) — None label = blank / identity
GROUP_HEADERS = [
    ('', 'no', 5),
    ('REGULAR PAY', 'reg_days', 4),
    ('OVERTIME PAY', 'ot_reg_hours', 6),
    ('SPECIAL NON WORKING DAY (+) 30%', 'snwd_days', 2),
    ('SN-W/SUNDAY', 'snw_sun_days', 2),
    ('REGULAR HOLIDAY', 'rh_days', 2),
    ('', 'gross_pay', 1),
    ('DEDUCTIONS', 'philhealth', 8),
    ('', 'net_pay', 1),
]

YELLOW_LEAF_KEYS = {
    'reg_days', 'ot_reg_hours', 'ot_sun_hours',
    'snwd_days', 'snw_sun_days', 'rh_days',
}


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), ROUND_HALF_UP)


def _hours(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), ROUND_HALF_UP)


def period_title(start: date, end: date) -> str:
    if start.year == end.year and start.month == end.month:
        return f'{start.strftime("%B").upper()} {start.day}-{end.day}, {start.year}'
    if start.year == end.year:
        return (
            f'{start.strftime("%B").upper()} {start.day} – '
            f'{end.strftime("%B").upper()} {end.day}, {start.year}'
        )
    return (
        f'{start.strftime("%B").upper()} {start.day}, {start.year} – '
        f'{end.strftime("%B").upper()} {end.day}, {end.year}'
    )


def holidays_in_cutoff(cutoff_start, cutoff_end) -> list[Holiday]:
    return list(
        Holiday.objects.filter(date__gte=cutoff_start, date__lte=cutoff_end).order_by('date')
    )


def classify_holiday_days(holidays: list[Holiday]) -> dict[str, int]:
    snwd = snw_sun = rh = 0
    for h in holidays:
        if h.type == 'regular':
            rh += 1
        elif h.type == 'special':
            if h.date.weekday() == 6:
                snw_sun += 1
            else:
                snwd += 1
    return {'snwd_days': snwd, 'snw_sun_days': snw_sun, 'rh_days': rh}


def sil_on_hand(employee: Employee) -> Decimal:
    bal = (
        LeaveBalance.objects.filter(employee=employee, leave_type='sil')
        .order_by('-as_of_date')
        .first()
    )
    if not bal:
        return ZERO
    remaining = Decimal(str(bal.balance_credits or 0)) - Decimal(str(bal.used_credits or 0))
    return remaining.quantize(Decimal('0.01'), ROUND_HALF_UP)


def ot_amounts_from_hours(ot_reg_hours, ot_sun_hours, hourly_rate: Decimal) -> dict[str, Decimal]:
    """Compute OT pesos from REG / SUN hours and hourly rate."""
    ot_reg = _hours(ot_reg_hours)
    ot_sun = _hours(ot_sun_hours)
    hourly = _money(hourly_rate)
    ot_reg_amount = _money(ot_reg * hourly * OT_REG_FACTOR)
    ot_sun_amount = _money(ot_sun * hourly * OT_SUN_FACTOR)
    return {
        'ot_reg_hours': ot_reg,
        'ot_reg_amount': ot_reg_amount,
        'ot_sun_hours': ot_sun,
        'ot_sun_amount': ot_sun_amount,
        'ot_total_hours': _hours(ot_reg + ot_sun),
        'ot_total_amount': _money(ot_reg_amount + ot_sun_amount),
        'overtime_hours': _hours(ot_reg + ot_sun),
        'overtime_pay': _money(ot_reg_amount + ot_sun_amount),
    }


def split_overtime_for_period(employee, cutoff_start, cutoff_end, hourly_rate: Decimal) -> dict[str, Decimal]:
    ot_reg = ZERO
    ot_sun = ZERO
    logs = get_attendance_for_period(employee, cutoff_start, cutoff_end)
    for log in logs:
        shift = get_effective_shift_schedule(employee, log.date)
        if not shift:
            continue
        _regular, overtime = compute_daily_hours(log, shift)
        if overtime <= 0:
            continue
        if log.date.weekday() == 6:
            ot_sun += overtime
        else:
            ot_reg += overtime
    return ot_amounts_from_hours(ot_reg, ot_sun, hourly_rate)


def holiday_pay_for_counts(daily: Decimal, counts: dict[str, int]) -> dict[str, Decimal | int]:
    snwd_days = int(counts.get('snwd_days') or 0)
    snw_sun_days = int(counts.get('snw_sun_days') or 0)
    rh_days = int(counts.get('rh_days') or 0)
    snwd_amount = _money(daily * Decimal(snwd_days) * SNWD_FACTOR)
    snw_sun_amount = _money(daily * Decimal(snw_sun_days) * SNW_SUNDAY_FACTOR)
    rh_amount = _money(daily * Decimal(rh_days) * REGULAR_HOLIDAY_FACTOR)
    return {
        'snwd_days': snwd_days,
        'snwd_amount': snwd_amount,
        'snw_sun_days': snw_sun_days,
        'snw_sun_amount': snw_sun_amount,
        'rh_days': rh_days,
        'rh_amount': rh_amount,
        'holiday_pay': _money(snwd_amount + snw_sun_amount + rh_amount),
    }


def compute_register_earnings(
    employee,
    cutoff_start,
    cutoff_end,
    *,
    lwp_days: int = 0,
    holiday_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Compute register earnings fields for one employee (used by compute_payroll)."""
    daily = estimated_daily_rate(employee)
    hourly = _money(daily / Decimal('8')) if daily else ZERO
    calendar_days = idle_calendar_days(cutoff_start, cutoff_end)
    reg_days = len(calendar_days)
    lwp = max(0, int(lwp_days or 0))
    total_days = max(0, reg_days - lwp)
    base_pay = _money(daily * Decimal(total_days))

    ot = split_overtime_for_period(employee, cutoff_start, cutoff_end, hourly)
    counts = holiday_counts if holiday_counts is not None else classify_holiday_days(
        holidays_in_cutoff(cutoff_start, cutoff_end)
    )
    hol = holiday_pay_for_counts(daily, counts)
    regular_hours = ZERO
    logs = get_attendance_for_period(employee, cutoff_start, cutoff_end)
    for log in logs:
        shift = get_effective_shift_schedule(employee, log.date)
        if shift:
            regular, _ot = compute_daily_hours(log, shift)
            regular_hours += regular

    gross = _money(base_pay + ot['overtime_pay'] + hol['holiday_pay'])
    return {
        'daily_rate': daily,
        'hourly_rate': hourly,
        'sil_on_hand': sil_on_hand(employee),
        'reg_days': reg_days,
        'lwp_days': lwp,
        'total_days': total_days,
        'reg_total': base_pay,
        'base_pay': base_pay,
        'regular_hours': _hours(regular_hours),
        **ot,
        **hol,
        'gross_pay': gross,
    }


def _bd(line: PayrollLine, key: str, default=0):
    bd = line.breakdown or {}
    if key in bd and bd[key] is not None:
        return bd[key]
    return default


def _row_from_line(index: int, line: PayrollLine, fallback_earnings: dict | None = None) -> dict[str, Any]:
    emp = line.employee
    fb = fallback_earnings or {}
    daily = _money(_bd(line, 'daily_rate', fb.get('daily_rate') or estimated_daily_rate(emp)))
    hourly = _money(_bd(line, 'hourly_rate', fb.get('hourly_rate') or (daily / Decimal('8') if daily else ZERO)))

    philhealth = _money(_bd(line, 'philhealth'))
    sss = _money(_bd(line, 'sss'))
    hdmf = _money(_bd(line, 'hdmf'))
    hdmf_loan = _money(_bd(line, 'hdmf_loan'))
    sss_loan = _money(_bd(line, 'sss_loan'))
    late_mins = int(_bd(line, 'undertime_minutes', fb.get('undertime_minutes') or 0) or 0)
    late_ut = _money(_bd(line, 'undertime_deduction', fb.get('undertime_deduction') or 0))
    total_ded = _money(philhealth + sss + hdmf + hdmf_loan + sss_loan + late_ut)

    reg_total = _money(_bd(line, 'base_pay', fb.get('base_pay') or line.gross_pay))
    snwd_amount = _money(_bd(line, 'snwd_amount', fb.get('snwd_amount') or 0))
    snw_sun_amount = _money(_bd(line, 'snw_sun_amount', fb.get('snw_sun_amount') or 0))
    rh_amount = _money(_bd(line, 'rh_amount', fb.get('rh_amount') or 0))

    # Prefer persisted PayrollLine OT hours; fall back to breakdown for pre-migration lines.
    ot_reg_h = line.ot_reg_hours or ZERO
    ot_sun_h = line.ot_sun_hours or ZERO
    if ot_reg_h == ZERO and ot_sun_h == ZERO:
        bd_reg = _bd(line, 'ot_reg_hours', None)
        bd_sun = _bd(line, 'ot_sun_hours', None)
        if bd_reg is not None or bd_sun is not None:
            ot_reg_h = bd_reg or 0
            ot_sun_h = bd_sun or 0
        elif fb:
            ot_reg_h = fb.get('ot_reg_hours') or 0
            ot_sun_h = fb.get('ot_sun_hours') or 0
    ot = ot_amounts_from_hours(ot_reg_h, ot_sun_h, hourly)
    ot_reg_amount = ot['ot_reg_amount']
    ot_sun_amount = ot['ot_sun_amount']
    ot_total_amount = ot['ot_total_amount']
    ot_total_hours = ot['ot_total_hours']
    if (
        _hours(_bd(line, 'ot_reg_hours', ot['ot_reg_hours'])) == ot['ot_reg_hours']
        and _hours(_bd(line, 'ot_sun_hours', ot['ot_sun_hours'])) == ot['ot_sun_hours']
        and _bd(line, 'ot_reg_amount', None) is not None
    ):
        ot_reg_amount = _money(_bd(line, 'ot_reg_amount'))
        ot_sun_amount = _money(_bd(line, 'ot_sun_amount'))
        ot_total_amount = _money(_bd(line, 'ot_total_amount', ot_reg_amount + ot_sun_amount))
        ot_total_hours = _hours(_bd(line, 'ot_total_hours', ot['ot_total_hours']))

    gross = _money(_bd(line, 'gross_pay', None) if _bd(line, 'gross_pay', None) is not None else line.gross_pay)
    if not gross and (reg_total or ot_total_amount):
        gross = _money(reg_total + ot_total_amount + snwd_amount + snw_sun_amount + rh_amount)

    net = _money(gross - total_ded)

    return {
        'no': index,
        'name': emp.full_name,
        'sil_on_hand': _money(_bd(line, 'sil_on_hand', fb.get('sil_on_hand') or sil_on_hand(emp))),
        'daily_rate': daily,
        'hourly_rate': hourly,
        'reg_days': int(_bd(line, 'reg_days', fb.get('reg_days') or 0) or 0),
        'lwp_days': int(_bd(line, 'lwp_days', _bd(line, 'absent_days', fb.get('lwp_days') or 0)) or 0),
        'total_days': int(_bd(line, 'total_days', fb.get('total_days') or 0) or 0),
        'reg_total': reg_total,
        'ot_reg_hours': ot['ot_reg_hours'],
        'ot_reg_amount': ot_reg_amount,
        'ot_sun_hours': ot['ot_sun_hours'],
        'ot_sun_amount': ot_sun_amount,
        'ot_total_hours': ot_total_hours,
        'ot_total_amount': ot_total_amount,
        'snwd_days': int(_bd(line, 'snwd_days', fb.get('snwd_days') or 0) or 0),
        'snwd_amount': snwd_amount,
        'snw_sun_days': int(_bd(line, 'snw_sun_days', fb.get('snw_sun_days') or 0) or 0),
        'snw_sun_amount': snw_sun_amount,
        'rh_days': int(_bd(line, 'rh_days', fb.get('rh_days') or 0) or 0),
        'rh_amount': rh_amount,
        'gross_pay': gross,
        'philhealth': philhealth,
        'sss': sss,
        'hdmf': hdmf,
        'hdmf_loan': hdmf_loan,
        'sss_loan': sss_loan,
        'late_ut_mins': late_mins,
        'late_ut_amount': late_ut,
        'total_deductions': total_ded,
        'net_pay': net,
        'employee_id': emp.id,
        'line_id': line.id,
    }


def _sum_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, Any] = {'no': '', 'name': 'TOTAL'}
    numeric_keys = [k for k, _ in LEAF_COLUMNS if k not in ('no', 'name')]
    for key in numeric_keys:
        if key in ('reg_days', 'lwp_days', 'total_days', 'snwd_days', 'snw_sun_days', 'rh_days', 'late_ut_mins'):
            totals[key] = sum(int(r.get(key) or 0) for r in rows)
        elif key.endswith('_hours') or key in ('ot_reg_hours', 'ot_sun_hours', 'ot_total_hours', 'sil_on_hand'):
            totals[key] = _hours(sum(Decimal(str(r.get(key) or 0)) for r in rows))
        else:
            totals[key] = _money(sum(Decimal(str(r.get(key) or 0)) for r in rows))
    return totals


def build_payroll_register(run: PayrollRun) -> dict[str, Any]:
    """Build register payload for PDF/Excel from a payroll run."""
    lines = list(
        PayrollLine.objects.filter(payroll_run=run)
        .select_related('employee')
        .order_by('employee__last_name', 'employee__first_name', 'employee__id')
    )
    holiday_counts = classify_holiday_days(
        holidays_in_cutoff(run.cutoff_start, run.cutoff_end)
    )
    rows = []
    for i, line in enumerate(lines, start=1):
        fb = None
        bd = line.breakdown or {}
        # Derive missing register fields on the fly for older lines, but never
        # override persisted OT hours on the PayrollLine itself.
        needs_earnings = 'reg_days' not in bd
        if needs_earnings:
            lwp = int(bd.get('absent_days') or bd.get('lwp_days') or 0)
            fb = compute_register_earnings(
                line.employee,
                run.cutoff_start,
                run.cutoff_end,
                lwp_days=lwp,
                holiday_counts=holiday_counts,
            )
            if 'undertime_minutes' in bd:
                fb['undertime_minutes'] = bd.get('undertime_minutes')
            if 'undertime_deduction' in bd:
                fb['undertime_deduction'] = bd.get('undertime_deduction')
        rows.append(_row_from_line(i, line, fb))

    return {
        'meta': {
            'run_id': run.id,
            'period_title': period_title(run.cutoff_start, run.cutoff_end),
            'cutoff_start': run.cutoff_start,
            'cutoff_end': run.cutoff_end,
            'status': run.status,
            'filename_stem': f'payroll_register_{run.cutoff_start.isoformat()}_{run.cutoff_end.isoformat()}',
        },
        'leaf_columns': LEAF_COLUMNS,
        'group_headers': GROUP_HEADERS,
        'yellow_leaf_keys': sorted(YELLOW_LEAF_KEYS),
        'rows': rows,
        'totals': _sum_rows(rows),
        'signatures': REGISTER_SIGNATURES,
    }
