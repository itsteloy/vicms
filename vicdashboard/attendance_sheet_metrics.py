"""Company schedule defaults and undertime/absence metrics for attendance sheets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import AttendanceSheet, AttendanceSheetEntry, AttendanceSheetPunch, Employee

VERSATEC_MARKER = 'VERSATEC'
DEFAULT_DAILY_RATE = Decimal('525.00')

MORNING_OUT = time(12, 0)
AFTERNOON_IN = time(13, 0)

VERSATEC_MORNING_IN = time(8, 0)
VERSATEC_MORNING_LATE_FROM = time(8, 11)
VERSATEC_AFTERNOON_OUT = time(17, 0)

OTHER_MORNING_IN = time(9, 0)
OTHER_MORNING_LATE_FROM = time(9, 11)
OTHER_AFTERNOON_OUT = time(16, 30)


@dataclass(frozen=True)
class ExpectedSchedule:
    morning_in: time
    morning_out: time
    afternoon_in: time
    afternoon_out: time
    morning_late_from: time
    is_versatec: bool

    def display(self, slot: time) -> str:
        return slot.strftime('%H:%M')


def is_versatec_company(company_name: str | None) -> bool:
    return VERSATEC_MARKER in (company_name or '').upper()


def get_expected_schedule(employee: Employee | None) -> ExpectedSchedule | None:
    if employee is None:
        return None
    company = getattr(employee, 'company', None)
    company_name = getattr(company, 'name', '') if company is not None else ''
    if is_versatec_company(company_name):
        return ExpectedSchedule(
            morning_in=VERSATEC_MORNING_IN,
            morning_out=MORNING_OUT,
            afternoon_in=AFTERNOON_IN,
            afternoon_out=VERSATEC_AFTERNOON_OUT,
            morning_late_from=VERSATEC_MORNING_LATE_FROM,
            is_versatec=True,
        )
    return ExpectedSchedule(
        morning_in=OTHER_MORNING_IN,
        morning_out=MORNING_OUT,
        afternoon_in=AFTERNOON_IN,
        afternoon_out=OTHER_AFTERNOON_OUT,
        morning_late_from=OTHER_MORNING_LATE_FROM,
        is_versatec=False,
    )


def parse_punch_time(value: str | None) -> time | None:
    """Parse punch strings like '08:21', '8:21', '8:21 AM' into time."""
    text = str(value or '').strip()
    if not text or text in {'—', '-', 'N/A', 'n/a'}:
        return None

    match = re.match(
        r'^(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM|am|pm)?$',
        text,
    )
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2))
    meridiem = match.group(4)
    if meridiem:
        meridiem = meridiem.upper()
        if meridiem == 'AM':
            if hour == 12:
                hour = 0
        elif meridiem == 'PM':
            if hour != 12:
                hour += 12
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def time_to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def format_minutes(total_minutes: int) -> str:
    minutes = max(int(total_minutes or 0), 0)
    if minutes == 0:
        return '0m'
    hours, rem = divmod(minutes, 60)
    if hours and rem:
        return f'{hours}h {rem}m'
    if hours:
        return f'{hours}h'
    return f'{rem}m'


def format_peso(amount: Decimal | int | float | None) -> str:
    value = Decimal(amount or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return f'₱{value:,.2f}'


def employee_daily_rate(employee: Employee | None) -> Decimal:
    if employee is None:
        return DEFAULT_DAILY_RATE
    rate = getattr(employee, 'daily_rate', None)
    if rate is None:
        return DEFAULT_DAILY_RATE
    return Decimal(rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def employee_hourly_rate(employee: Employee | None) -> Decimal:
    return (employee_daily_rate(employee) / Decimal('8')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )


def is_sunday_punch(punch: AttendanceSheetPunch) -> bool:
    punch_date = getattr(punch, 'punch_date', None)
    return punch_date is not None and punch_date.weekday() == 6


def _slot_filled(value: str | None) -> bool:
    return bool(str(value or '').strip())


def day_has_attendance(punch: AttendanceSheetPunch) -> bool:
    return any(
        _slot_filled(slot)
        for slot in (
            punch.morning_in,
            punch.morning_out,
            punch.afternoon_in,
            punch.afternoon_out,
        )
    )


def compute_punch_metrics(
    punch: AttendanceSheetPunch,
    schedule: ExpectedSchedule | None,
    *,
    is_ob_day: bool = False,
) -> dict[str, Any]:
    """Return derived metrics for one punch day."""
    empty = {
        'expected_morning_in': '—',
        'expected_morning_out': '—',
        'expected_afternoon_in': '—',
        'expected_afternoon_out': '—',
        'undertime_minutes': 0,
        'undertime_display': '—',
        'is_absent': False,
        'is_mapped': False,
        'is_sunday': is_sunday_punch(punch),
        'is_official_business': False,
    }
    if schedule is None:
        return empty

    expected = {
        'expected_morning_in': schedule.display(schedule.morning_in),
        'expected_morning_out': schedule.display(schedule.morning_out),
        'expected_afternoon_in': schedule.display(schedule.afternoon_in),
        'expected_afternoon_out': schedule.display(schedule.afternoon_out),
        'is_mapped': True,
        'is_sunday': is_sunday_punch(punch),
        'is_official_business': False,
    }

    if not day_has_attendance(punch):
        # Blank Sundays and approved Official Business days are not absences.
        is_absent = not (expected['is_sunday'] or is_ob_day)
        return {
            **expected,
            'undertime_minutes': 0,
            'undertime_display': '0m',
            'is_absent': is_absent,
            'is_official_business': bool(is_ob_day),
        }

    morning_undertime = 0
    actual_morning_in = parse_punch_time(punch.morning_in)
    if actual_morning_in is not None:
        morning_undertime = max(
            time_to_minutes(actual_morning_in) - time_to_minutes(schedule.morning_late_from),
            0,
        )

    afternoon_undertime = 0
    actual_afternoon_out = parse_punch_time(punch.afternoon_out)
    if actual_afternoon_out is None:
        # Incomplete day: assume scheduled company end (no early-out undertime).
        actual_afternoon_out = schedule.afternoon_out
    afternoon_undertime = max(
        time_to_minutes(schedule.afternoon_out) - time_to_minutes(actual_afternoon_out),
        0,
    )

    total = morning_undertime + afternoon_undertime
    return {
        **expected,
        'undertime_minutes': total,
        'undertime_display': format_minutes(total),
        'is_absent': False,
    }


def _unmapped_entry_metrics() -> dict[str, Any]:
    return {
        'is_mapped': False,
        'company_name': '—',
        'total_undertime_minutes': 0,
        'total_undertime_display': '—',
        'absent_days': 0,
        'ob_days': 0,
        'expected_morning_in': '—',
        'expected_morning_out': '—',
        'expected_afternoon_in': '—',
        'expected_afternoon_out': '—',
        'daily_rate': None,
        'hourly_rate': None,
        'daily_rate_display': '—',
        'hourly_rate_display': '—',
        'undertime_deduction': Decimal('0.00'),
        'undertime_deduction_display': '—',
        'absence_deduction': Decimal('0.00'),
        'absence_deduction_display': '—',
        'total_deduction': Decimal('0.00'),
        'total_deduction_display': '—',
    }


def annotate_attendance_sheet(sheet: AttendanceSheet | None) -> AttendanceSheet | None:
    """Attach derived metrics to entries and punches on the selected sheet."""
    if sheet is None:
        return None

    from .official_business import ob_dates_by_employee_id

    mapped_employees = [
        entry.linked_employee
        for entry in sheet.entries.all()
        if entry.linked_employee_id is not None
    ]
    period_start = getattr(sheet, 'period_start', None)
    period_end = getattr(sheet, 'period_end', None)
    if period_start is None or period_end is None:
        punch_dates = [
            punch.punch_date
            for entry in sheet.entries.all()
            for punch in entry.punches.all()
            if punch.punch_date is not None
        ]
        if punch_dates:
            period_start = period_start or min(punch_dates)
            period_end = period_end or max(punch_dates)

    ob_by_employee = ob_dates_by_employee_id(
        mapped_employees,
        date_start=period_start,
        date_end=period_end,
    )

    for entry in sheet.entries.all():
        employee = entry.linked_employee
        schedule = get_expected_schedule(employee) if employee else None
        company_name = ''
        if employee is not None and getattr(employee, 'company', None) is not None:
            company_name = employee.company.name

        total_undertime = 0
        absent_days = 0
        ob_days = 0
        emp_ob_dates = ob_by_employee.get(employee.id, set()) if employee else set()

        for punch in entry.punches.all():
            is_ob = bool(punch.punch_date and punch.punch_date in emp_ob_dates)
            metrics = compute_punch_metrics(punch, schedule, is_ob_day=is_ob)
            punch.metrics = metrics
            if schedule is not None:
                total_undertime += metrics['undertime_minutes']
                if metrics['is_absent']:
                    absent_days += 1
                if metrics.get('is_official_business'):
                    ob_days += 1

        if schedule is None:
            entry.metrics = _unmapped_entry_metrics()
            continue

        daily = employee_daily_rate(employee)
        hourly = employee_hourly_rate(employee)
        undertime_hours = (Decimal(total_undertime) / Decimal('60'))
        undertime_deduction = (undertime_hours * hourly).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        absence_deduction = (Decimal(absent_days) * daily).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        total_deduction = (undertime_deduction + absence_deduction).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        entry.metrics = {
            'is_mapped': True,
            'company_name': company_name or '—',
            'total_undertime_minutes': total_undertime,
            'total_undertime_display': format_minutes(total_undertime),
            'absent_days': absent_days,
            'ob_days': ob_days,
            'expected_morning_in': schedule.display(schedule.morning_in),
            'expected_morning_out': schedule.display(schedule.morning_out),
            'expected_afternoon_in': schedule.display(schedule.afternoon_in),
            'expected_afternoon_out': schedule.display(schedule.afternoon_out),
            'daily_rate': daily,
            'hourly_rate': hourly,
            'daily_rate_display': format_peso(daily),
            'hourly_rate_display': format_peso(hourly),
            'undertime_deduction': undertime_deduction,
            'undertime_deduction_display': format_peso(undertime_deduction),
            'absence_deduction': absence_deduction,
            'absence_deduction_display': format_peso(absence_deduction),
            'total_deduction': total_deduction,
            'total_deduction_display': format_peso(total_deduction),
        }

    return sheet
