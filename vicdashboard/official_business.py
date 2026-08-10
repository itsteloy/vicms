"""Official Business date helpers for attendance / payroll."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Iterable

from .models import OfficialBusinessForm

if TYPE_CHECKING:
    from .models import Employee


def normalize_ob_dates(ob_dates_text: str | None) -> set[date]:
    """Parse newline-separated ISO dates (YYYY-MM-DD) from OfficialBusinessForm.ob_dates."""
    result: set[date] = set()
    for line in (ob_dates_text or '').splitlines():
        value = line.strip()
        if not value:
            continue
        try:
            result.add(date.fromisoformat(value))
        except ValueError:
            # Ignore free-text / non-ISO lines (edit form may allow them).
            try:
                result.add(datetime.strptime(value, '%Y-%m-%d').date())
            except ValueError:
                continue
    return result


def _name_key(value: str | None) -> str:
    return ' '.join((value or '').strip().upper().split())


def employee_ob_dates(
    employee: Employee,
    date_start: date | None = None,
    date_end: date | None = None,
) -> set[date]:
    """Approved OB dates for one employee (matched by full_name)."""
    full = getattr(employee, 'full_name', '') or ''
    key = _name_key(full)
    if not key:
        return set()

    dates: set[date] = set()
    for ob in OfficialBusinessForm.objects.filter(status='approved').only('name', 'ob_dates'):
        if _name_key(ob.name) != key:
            continue
        for day in normalize_ob_dates(ob.ob_dates):
            if date_start is not None and day < date_start:
                continue
            if date_end is not None and day > date_end:
                continue
            dates.add(day)
    return dates


def is_official_business_day(employee: Employee, day: date) -> bool:
    return day in employee_ob_dates(employee, date_start=day, date_end=day)


def ob_dates_by_employee_id(
    employees: Iterable[Employee],
    date_start: date | None = None,
    date_end: date | None = None,
) -> dict[int, set[date]]:
    """
    Bulk map employee.id -> set of approved OB dates in [date_start, date_end].

    Matching is case-insensitive on OfficialBusinessForm.name == Employee.full_name.
    """
    employees = list(employees)
    if not employees:
        return {}

    name_to_ids: dict[str, list[int]] = {}
    for emp in employees:
        key = _name_key(getattr(emp, 'full_name', '') or '')
        if not key:
            continue
        name_to_ids.setdefault(key, []).append(emp.id)

    if not name_to_ids:
        return {emp.id: set() for emp in employees}

    result: dict[int, set[date]] = {emp.id: set() for emp in employees}
    for ob in OfficialBusinessForm.objects.filter(status='approved').only('name', 'ob_dates'):
        key = _name_key(ob.name)
        emp_ids = name_to_ids.get(key)
        if not emp_ids:
            continue
        for day in normalize_ob_dates(ob.ob_dates):
            if date_start is not None and day < date_start:
                continue
            if date_end is not None and day > date_end:
                continue
            for emp_id in emp_ids:
                result[emp_id].add(day)
    return result
