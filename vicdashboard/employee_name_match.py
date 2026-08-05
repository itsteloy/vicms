"""Match attendance-sheet device names to Employee records by name."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

from .models import AttendanceSheetEntry, Employee

# When the same EMP matches multiple sheet rows, prefer these device IDs.
PREFERRED_DEVICE_IDS = {
    '00000039',  # Vicente_Malias → EMP-020
    '00000008',  # Noval_Marlon → EMP-024
    '00000034',  # Beverly_Tan → EMP-033
}


def normalize_name(value: str) -> str:
    text = (value or '').upper().strip()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace('_', ' ').replace('.', ' ').replace('-', ' ')
    text = re.sub(r'[^A-Z0-9 ]', ' ', text)
    return re.sub(r' +', ' ', text).strip()


def split_device_name(raw: str) -> list[str]:
    """Split camelCase / underscored device names into tokens."""
    text = raw or ''
    parts: list[str] = []
    buf = ''
    for index, ch in enumerate(text):
        if ch in '._- ':
            if buf:
                parts.append(buf)
                buf = ''
            continue
        if buf and ch.isupper() and buf[-1].islower():
            parts.append(buf)
            buf = ch
        elif (
            buf
            and ch.isupper()
            and len(buf) > 1
            and buf[-1].isupper()
            and index + 1 < len(text)
            and text[index + 1].islower()
        ):
            parts.append(buf)
            buf = ch
        else:
            buf += ch
    if buf:
        parts.append(buf)
    return parts


def score_name_match(
    sheet_name: str,
    employee: Employee,
    last_counts: Counter,
    first_counts: Counter,
) -> tuple[int, str]:
    """Return (score, reason). Score < 55 means no usable match."""
    last = normalize_name(employee.last_name)
    first_parts = normalize_name(employee.first_name).split()
    first = first_parts[0] if first_parts else ''
    initials = ''.join(part[0] for part in first_parts)

    parts = [normalize_name(part) for part in split_device_name(sheet_name)]
    parts = [part for part in parts if part]
    compact = ''.join(parts)

    score = 0
    reason = ''

    if last and last in parts:
        score += 50
        reason = 'last'
        if any(part in parts for part in first_parts):
            score += 40
            reason = 'last+first'
        elif initials and (initials in parts or initials in compact):
            score += 35
            reason = 'last+initials'
        elif first and any(part == first[0] for part in parts):
            score += 25
            reason = 'last+init'
        elif last_counts[last] == 1 and len(parts) == 1:
            score += 20
            reason = 'unique-last-only'

    if last and first and (
        last + first in compact
        or first + last in compact
        or (initials and last + initials in compact)
    ):
        score = max(score, 95)
        reason = 'compact'

    if score < 50 and first_parts and all(part in parts or part in compact for part in first_parts):
        score = max(score, 60)
        reason = 'first-parts'

    if score < 50 and first and (first in parts or first in compact) and len(first) >= 4:
        if first_counts.get(first, 0) == 1:
            score = max(score, 70)
            reason = 'unique-first'

    if score < 50 and last and last in compact and len(last) >= 5:
        score = max(score, 55)
        reason = 'last-compact'
        if first and first[:4] in compact:
            score = max(score, 90)
            reason = 'last+first-compact'

    if score < 70 and last and last in compact:
        for part in first_parts:
            if len(part) >= 4 and part[:4] in compact:
                score = max(score, 88)
                reason = 'last+first4'

    if score < 70 and first and len(first) >= 4:
        rough = first[:4]
        if rough in compact and last_counts.get(last, 0) == 1:
            if last and (last in compact or (last and last[0] in compact)):
                score = max(score, 72)
                reason = 'approx-first+lasthint'
            elif first_counts.get(first, 0) == 1:
                score = max(score, 68)
                reason = 'approx-unique-first'

    return score, reason


def best_employee_for_sheet_name(
    sheet_name: str,
    employees: list[Employee],
    last_counts: Counter | None = None,
    first_counts: Counter | None = None,
) -> tuple[Employee | None, int, str]:
    if last_counts is None:
        last_counts = Counter(normalize_name(emp.last_name) for emp in employees)
    if first_counts is None:
        first_counts = Counter(
            normalize_name(emp.first_name).split()[0]
            for emp in employees
            if normalize_name(emp.first_name).split()
        )

    best: Employee | None = None
    best_score = 0
    best_reason = ''
    for emp in employees:
        score, reason = score_name_match(sheet_name, emp, last_counts, first_counts)
        if score > best_score:
            best = emp
            best_score = score
            best_reason = reason
    if best_score < 55:
        return None, 0, ''
    return best, best_score, best_reason


def link_attendance_entries(
    entries: list[AttendanceSheetEntry] | None = None,
    *,
    clear_existing: bool = True,
) -> dict:
    """
    Set linked_employee on sheet entries by name match.
    At most one entry per employee; preferred device IDs win ties.
    """
    employees = list(Employee.objects.all())
    if entries is None:
        entries = list(AttendanceSheetEntry.objects.all())
    else:
        entries = list(entries)

    if not entries:
        return {'linked': 0, 'entries': 0, 'employees': len(employees)}

    if clear_existing:
        AttendanceSheetEntry.objects.filter(
            id__in=[entry.id for entry in entries]
        ).update(linked_employee=None)
        for entry in entries:
            entry.linked_employee = None

    last_counts = Counter(normalize_name(emp.last_name) for emp in employees)
    first_counts = Counter(
        normalize_name(emp.first_name).split()[0]
        for emp in employees
        if normalize_name(emp.first_name).split()
    )

    candidates: list[tuple[AttendanceSheetEntry, Employee, int, str]] = []
    for entry in entries:
        emp, score, reason = best_employee_for_sheet_name(
            entry.employee_name,
            employees,
            last_counts=last_counts,
            first_counts=first_counts,
        )
        if emp is None:
            continue
        bonus = 0
        if (entry.device_employee_id or '') in PREFERRED_DEVICE_IDS:
            bonus += 20
        bonus += min(len(entry.employee_name or ''), 40) // 8
        candidates.append((entry, emp, score + bonus, reason))

    by_employee: dict[int, list[tuple[AttendanceSheetEntry, Employee, int, str]]] = defaultdict(list)
    for item in candidates:
        by_employee[item[1].id].append(item)

    linked = 0
    for items in by_employee.values():
        items.sort(
            key=lambda row: (
                -row[2],
                0 if (row[0].device_employee_id or '') in PREFERRED_DEVICE_IDS else 1,
                -len(row[0].employee_name or ''),
            )
        )
        entry, emp, _score, _reason = items[0]
        entry.linked_employee = emp
        entry.save(update_fields=['linked_employee'])
        linked += 1

    return {
        'linked': linked,
        'entries': len(entries),
        'employees': len(employees),
    }
