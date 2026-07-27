from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Q

from .models import EmployeeDeduction, TaxBracket


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
        bracket = TaxBracket.objects.filter(
            tax_type=tax_type,
            effective_date__lte=cutoff_date,
        ).order_by('-effective_date').first()
        if bracket:
            total += gross_pay * bracket.tax_rate
    return total


def get_voluntary_deductions(employee, cutoff_start, cutoff_end):
    deductions = EmployeeDeduction.objects.filter(
        employee=employee,
        start_date__lte=cutoff_end,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=cutoff_start)
    )
    total = Decimal('0')
    for ded in deductions:
        total += ded.amount
    return total
