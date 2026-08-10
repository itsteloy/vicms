"""Attendance-sheet undertime/absence deductions for payroll compute."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db.models import Q

from .attendance_sheet_metrics import (
    compute_punch_metrics,
    employee_daily_rate,
    employee_hourly_rate,
    get_expected_schedule,
)
from .models import AttendanceSheet, AttendanceSheetPunch, Employee


ZERO = Decimal('0.00')


def _empty_deduction_result() -> dict[str, Any]:
    return {
        'undertime_minutes': 0,
        'undertime_hours': ZERO,
        'undertime_deduction': ZERO,
        'absent_days': 0,
        'absence_deduction': ZERO,
        'attendance_deduction': ZERO,
        'attendance_sheet_ids': [],
        'punch_days': 0,
    }


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def overlapping_attendance_sheets(cutoff_start: date, cutoff_end: date):
    """Sheets whose declared period overlaps the cutoff, or that have punches in range."""
    period_overlap = Q(
        period_start__isnull=False,
        period_end__isnull=False,
        period_start__lte=cutoff_end,
        period_end__gte=cutoff_start,
    )
    punch_overlap = Q(
        entries__punches__punch_date__gte=cutoff_start,
        entries__punches__punch_date__lte=cutoff_end,
    )
    return (
        AttendanceSheet.objects.filter(period_overlap | punch_overlap)
        .distinct()
        .order_by('-uploaded_at', '-id')
    )


def count_unmapped_entries_in_sheets(sheet_ids: list[int]) -> int:
    if not sheet_ids:
        return 0
    from .models import AttendanceSheetEntry

    return AttendanceSheetEntry.objects.filter(
        sheet_id__in=sheet_ids,
        linked_employee__isnull=True,
    ).count()


def load_attendance_deductions_by_employee(
    cutoff_start: date,
    cutoff_end: date,
    *,
    sheet_ids: list[int] | None = None,
) -> tuple[dict[int, dict[str, Any]], list[int], int]:
    """
    Bulk-load punch sheets and roll up attendance deductions per employee.

    If `sheet_ids` is provided (even empty), only those sheets are used.
    If `sheet_ids` is None, sheets overlapping the cutoff are auto-selected.

    Returns:
      (by_employee_id, sheet_ids_used, unmapped_entry_count)
    """
    if sheet_ids is not None:
        # Preserve caller order uniqueness while keeping only existing IDs.
        requested = []
        seen: set[int] = set()
        for raw in sheet_ids:
            try:
                sid = int(raw)
            except (TypeError, ValueError):
                continue
            if sid in seen:
                continue
            seen.add(sid)
            requested.append(sid)
        existing = set(
            AttendanceSheet.objects.filter(id__in=requested).values_list('id', flat=True)
        )
        sheet_ids = [sid for sid in requested if sid in existing]
    else:
        sheets = list(overlapping_attendance_sheets(cutoff_start, cutoff_end))
        sheet_ids = [sheet.id for sheet in sheets]

    if not sheet_ids:
        return {}, [], 0

    unmapped_count = count_unmapped_entries_in_sheets(sheet_ids)

    punches = (
        AttendanceSheetPunch.objects.filter(
            entry__sheet_id__in=sheet_ids,
            entry__linked_employee_id__isnull=False,
            punch_date__gte=cutoff_start,
            punch_date__lte=cutoff_end,
        )
        .select_related(
            'entry',
            'entry__sheet',
            'entry__linked_employee',
            'entry__linked_employee__company',
        )
        .order_by(
            'entry__linked_employee_id',
            'punch_date',
            '-entry__sheet__uploaded_at',
            '-entry__sheet_id',
            '-id',
        )
    )

    # De-dupe by (employee_id, punch_date); first row wins due to ordering.
    best_punches: dict[tuple[int, date], AttendanceSheetPunch] = {}
    for punch in punches:
        employee_id = punch.entry.linked_employee_id
        punch_date = punch.punch_date
        if employee_id is None or punch_date is None:
            continue
        key = (employee_id, punch_date)
        if key not in best_punches:
            best_punches[key] = punch

    # Group de-duped punches by employee.
    punches_by_employee: dict[int, list[AttendanceSheetPunch]] = {}
    for (employee_id, _), punch in best_punches.items():
        punches_by_employee.setdefault(employee_id, []).append(punch)

    from .official_business import ob_dates_by_employee_id

    employees = [
        punches_by_employee[eid][0].entry.linked_employee
        for eid in punches_by_employee
    ]
    ob_by_employee = ob_dates_by_employee_id(
        employees,
        date_start=cutoff_start,
        date_end=cutoff_end,
    )

    by_employee: dict[int, dict[str, Any]] = {}
    for employee_id, emp_punches in punches_by_employee.items():
        employee = emp_punches[0].entry.linked_employee
        by_employee[employee_id] = _rollup_employee_punches(
            employee,
            emp_punches,
            ob_dates=ob_by_employee.get(employee_id, set()),
        )

    return by_employee, sheet_ids, unmapped_count


def _rollup_employee_punches(
    employee: Employee,
    punches: list[AttendanceSheetPunch],
    *,
    ob_dates: set[date] | None = None,
) -> dict[str, Any]:
    schedule = get_expected_schedule(employee)
    if schedule is None:
        return _empty_deduction_result()

    total_undertime = 0
    absent_days = 0
    sheet_ids: set[int] = set()
    emp_ob_dates = ob_dates or set()

    for punch in punches:
        is_ob = bool(punch.punch_date and punch.punch_date in emp_ob_dates)
        metrics = compute_punch_metrics(punch, schedule, is_ob_day=is_ob)
        total_undertime += int(metrics.get('undertime_minutes') or 0)
        if metrics.get('is_absent'):
            absent_days += 1
        sheet_ids.add(punch.entry.sheet_id)

    daily = employee_daily_rate(employee)
    hourly = employee_hourly_rate(employee)
    undertime_hours = (Decimal(total_undertime) / Decimal('60'))
    undertime_deduction = _money(undertime_hours * hourly)
    absence_deduction = _money(Decimal(absent_days) * daily)
    attendance_deduction = _money(undertime_deduction + absence_deduction)

    return {
        'undertime_minutes': total_undertime,
        'undertime_hours': _money(undertime_hours),
        'undertime_deduction': undertime_deduction,
        'absent_days': absent_days,
        'absence_deduction': absence_deduction,
        'attendance_deduction': attendance_deduction,
        'attendance_sheet_ids': sorted(sheet_ids),
        'punch_days': len(punches),
    }


def attendance_deductions_for_employee(
    employee: Employee,
    cutoff_start: date,
    cutoff_end: date,
    *,
    preloaded: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Return undertime/absence deduction totals for one employee in a cutoff window.

    Prefer passing `preloaded` from `load_attendance_deductions_by_employee` when
    computing many employees.
    """
    if preloaded is not None:
        return preloaded.get(employee.id, _empty_deduction_result())

    by_employee, _, _ = load_attendance_deductions_by_employee(
        cutoff_start,
        cutoff_end,
        sheet_ids=None,
    )
    return by_employee.get(employee.id, _empty_deduction_result())
