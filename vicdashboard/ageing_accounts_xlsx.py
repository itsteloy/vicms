"""Parse Ageing of Accounts Excel workbooks into structured report data."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

HEADER_ALIASES = {
    'date': 'line_date',
    'customers name': 'customer_name',
    'customer name': 'customer_name',
    'po no.': 'po_number',
    'po no': 'po_number',
    'agent': 'agent',
    'bi#': 'bi_number',
    'si#': 'si_number',
    'cr#': 'cr_number',
    'ci#': 'ci_number',
    'ar#': 'ar_number',
    'dr no.': 'dr_number',
    'dr no': 'dr_number',
    'terms of payment': 'terms_of_payment',
    'terms': 'terms_of_payment',
    'payment terms': 'terms_of_payment',
    'amount': 'amount',
    'amount paid': 'amount_paid',
    'paid items': 'paid_items',
}

TERMS_OF_PAYMENT_VALUES = {'7', '15', '30', '60'}


def _normalize_header(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip().lower())


def _excel_serial_to_date(serial: float) -> date:
    base = datetime(1899, 12, 30)
    return (base + timedelta(days=float(serial))).date()


def _parse_date_value(value: Any) -> tuple[date | None, str]:
    if value is None or value == '':
        return None, ''
    if isinstance(value, datetime):
        return value.date(), ''
    if isinstance(value, date):
        return value, ''
    text = str(value).strip()
    if not text:
        return None, ''
    upper = text.upper()
    if upper in {'NO DATE', 'N/A', '-', '—'}:
        return None, text
    try:
        serial = float(text)
        if 30000 < serial < 60000:
            return _excel_serial_to_date(serial), ''
    except (TypeError, ValueError):
        pass
    for fmt in ('%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(text, fmt).date(), ''
        except ValueError:
            continue
    return None, text


def _parse_amount_value(value: Any) -> tuple[Decimal | None, str]:
    if value is None or value == '':
        return None, ''
    text = str(value).strip()
    if not text:
        return None, ''
    cleaned = text.replace(',', '').replace('₱', '').replace('PHP', '').strip()
    try:
        return Decimal(cleaned), ''
    except (InvalidOperation, ValueError):
        return None, text


def _cell_text(value: Any) -> str:
    if value is None:
        return ''
    text = str(value).strip()
    if re.fullmatch(r'\d+\.0', text):
        return text[:-2]
    return text


def _normalize_terms_of_payment(value: Any) -> str:
    text = _cell_text(value).strip().lower()
    if not text:
        return ''
    if text in TERMS_OF_PAYMENT_VALUES:
        return text
    match = re.search(r'\b(7|15|30|60)\b', text)
    if match and match.group(1) in TERMS_OF_PAYMENT_VALUES:
        return match.group(1)
    return ''


def _read_xlsx_rows(path: Path) -> list[list[Any]]:
    try:
        workbook = load_workbook(path, data_only=True, read_only=True)
    except (BadZipFile, InvalidFileException, OSError, ValueError, KeyError) as exc:
        raise ValueError('Unable to read this Excel workbook. Please upload a valid .xlsx file.') from exc
    try:
        return [list(row) for row in workbook.active.iter_rows(values_only=True)]
    finally:
        workbook.close()


def _extract_as_of_date(rows: list[list[Any]]) -> date | None:
    for row in rows[:12]:
        text = ' '.join(str(value) for value in row if value is not None)
        match = re.search(
            r'\b([A-Za-z]+)\s+(\d{1,2})\s*,?\s+(\d{4})\b',
            text,
        )
        if not match:
            continue
        month, day, year = match.groups()
        for month_format in ('%B', '%b'):
            try:
                return datetime.strptime(
                    f'{month} {day} {year}',
                    f'{month_format} %d %Y',
                ).date()
            except ValueError:
                continue
    return None


def parse_ageing_accounts_xlsx(path: Path) -> dict:
    rows = _read_xlsx_rows(path)
    if not rows:
        return {
            'lines': [],
            'total_amount': Decimal('0'),
            'total_amount_paid': Decimal('0'),
            'as_of_date': None,
            'source_filename': path.name,
        }

    header_index = None
    col_map: dict[int, str] = {}
    for row_index, row in enumerate(rows):
        candidate = {}
        for index, header in enumerate(row):
            key = _normalize_header(header)
            if key in HEADER_ALIASES:
                candidate[index] = HEADER_ALIASES[key]
        fields = set(candidate.values())
        if 'customer_name' in fields and 'amount' in fields:
            header_index = row_index
            col_map = candidate
            break
    if header_index is None:
        return {
            'lines': [],
            'total_amount': Decimal('0'),
            'total_amount_paid': Decimal('0'),
            'as_of_date': _extract_as_of_date(rows),
            'source_filename': path.name,
        }

    lines = []
    total_amount: Decimal | None = None
    total_amount_paid: Decimal | None = None

    for row in rows[header_index + 1:]:
        if not row:
            continue
        record: dict[str, Any] = {field: '' for field in HEADER_ALIASES.values()}
        for col_index, field in col_map.items():
            value = row[col_index] if col_index < len(row) else ''
            if field in {'amount', 'amount_paid', 'line_date'}:
                continue
            record[field] = _cell_text(value)

        customer = (record.get('customer_name') or '').strip()
        if not customer:
            continue
        if customer.upper() == 'GRAND TOTAL':
            amount_col = next((i for i, f in col_map.items() if f == 'amount'), None)
            paid_col = next((i for i, f in col_map.items() if f == 'amount_paid'), None)
            if amount_col is not None and amount_col < len(row):
                parsed, _ = _parse_amount_value(row[amount_col])
                if parsed is not None:
                    total_amount = parsed
            if paid_col is not None and paid_col < len(row):
                parsed, _ = _parse_amount_value(row[paid_col])
                if parsed is not None:
                    total_amount_paid = parsed
            continue

        date_col = next((i for i, f in col_map.items() if f == 'line_date'), 0)
        date_value = row[date_col] if date_col < len(row) else ''
        line_date, line_date_raw = _parse_date_value(date_value)

        amount_col = next((i for i, f in col_map.items() if f == 'amount'), None)
        paid_col = next((i for i, f in col_map.items() if f == 'amount_paid'), None)
        amount_value = row[amount_col] if amount_col is not None and amount_col < len(row) else ''
        paid_value = row[paid_col] if paid_col is not None and paid_col < len(row) else ''
        amount, amount_raw = _parse_amount_value(amount_value)
        amount_paid, amount_paid_raw = _parse_amount_value(paid_value)

        lines.append({
            'line_date': line_date,
            'line_date_raw': line_date_raw,
            'customer_name': customer,
            'po_number': record.get('po_number', ''),
            'agent': record.get('agent', ''),
            'bi_number': record.get('bi_number', ''),
            'si_number': record.get('si_number', ''),
            'cr_number': record.get('cr_number', ''),
            'ci_number': record.get('ci_number', ''),
            'ar_number': record.get('ar_number', ''),
            'dr_number': record.get('dr_number', ''),
            'terms_of_payment': _normalize_terms_of_payment(record.get('terms_of_payment', '')),
            'amount': amount,
            'amount_raw': amount_raw,
            'amount_paid': amount_paid,
            'amount_paid_raw': amount_paid_raw,
            'paid_items': record.get('paid_items', ''),
            'sort_order': len(lines),
        })

    if total_amount is None:
        total_amount = sum((line['amount'] or Decimal('0') for line in lines), Decimal('0'))
    if total_amount_paid is None:
        total_amount_paid = sum((line['amount_paid'] or Decimal('0') for line in lines), Decimal('0'))

    total_amount = Decimal(total_amount).quantize(Decimal('0.01'))
    total_amount_paid = Decimal(total_amount_paid).quantize(Decimal('0.01'))

    return {
        'lines': lines,
        'total_amount': total_amount,
        'total_amount_paid': total_amount_paid,
        'as_of_date': _extract_as_of_date(rows),
        'source_filename': path.name,
    }
