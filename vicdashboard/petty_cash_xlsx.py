"""Parse Petty Cash / Revolving Fund Excel workbooks into structured report data."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from vicdashboard.ageing_accounts_xlsx import (
    _cell_text,
    _normalize_header,
    _parse_amount_value,
    _parse_date_value,
    _read_xlsx_rows,
)

MONEY_FIELDS = (
    'cash_in_bank',
    'input_tax',
    'fuel',
    'fare',
    'lodging',
    'meal',
    'purchases',
    'repair',
    'freight',
    'meeting',
    'office',
    'communication',
    'bidding',
    'fines',
    'misc',
)

HEADER_ALIASES = {
    'date': 'line_date',
    'particulars': 'particulars',
    'explanation': 'explanation',
    'tin': 'tin',
    'pcv#': 'pcv_number',
    'pcv': 'pcv_number',
    'pcv no': 'pcv_number',
    'pcv no.': 'pcv_number',
    'cash in bank': 'cash_in_bank',
    'input tax': 'input_tax',
    'fuel': 'fuel',
    'fuel & lubricant': 'fuel',
    'fuel and lubricant': 'fuel',
    'fare': 'fare',
    'fare / transpo': 'fare',
    'fare/transpo': 'fare',
    'transpo': 'fare',
    'lodging': 'lodging',
    'meal': 'meal',
    'meals': 'meal',
    'purchases': 'purchases',
    'repair': 'repair',
    'repair & maint.': 'repair',
    'repair & maint': 'repair',
    'repair and maint': 'repair',
    'freight': 'freight',
    'meeting': 'meeting',
    'office': 'office',
    'office supplies': 'office',
    'communication': 'communication',
    'bidding': 'bidding',
    'fines': 'fines',
    'misc': 'misc',
    'miscellaneous': 'misc',
}


def parse_petty_cash_xlsx(path: Path) -> dict:
    rows = _read_xlsx_rows(path)
    if not rows:
        return {
            'lines': [],
            'total_cash_in_bank': Decimal('0'),
            'source_filename': path.name,
        }

    header_row_index = 0
    col_map: dict[int, str] = {}
    for idx, row in enumerate(rows[:5]):
        mapped = {}
        for index, header in enumerate(row):
            key = HEADER_ALIASES.get(_normalize_header(header))
            if key:
                mapped[index] = key
        if 'particulars' in mapped.values() or 'pcv_number' in mapped.values() or 'cash_in_bank' in mapped.values():
            header_row_index = idx
            col_map = mapped
            break

    lines = []
    total_cash = Decimal('0')
    found_total = False

    for row in rows[header_row_index + 1:]:
        if not row:
            continue
        record: dict[str, Any] = {field: '' for field in set(HEADER_ALIASES.values())}
        for col_index, field in col_map.items():
            value = row[col_index] if col_index < len(row) else ''
            if field in MONEY_FIELDS or field == 'line_date':
                continue
            record[field] = _cell_text(value)

        particulars = (record.get('particulars') or '').strip()
        explanation = (record.get('explanation') or '').strip()
        pcv = (record.get('pcv_number') or '').strip()
        label = (particulars or explanation or pcv).upper()
        if label in {'TOTAL', 'GRAND TOTAL', 'TOTAL CASH IN BANK'}:
            cash_col = next((i for i, f in col_map.items() if f == 'cash_in_bank'), None)
            if cash_col is not None and cash_col < len(row):
                parsed, _ = _parse_amount_value(row[cash_col])
                if parsed is not None:
                    total_cash = parsed.quantize(Decimal('0.01'))
                    found_total = True
            continue

        money_values = {}
        for field in MONEY_FIELDS:
            col = next((i for i, f in col_map.items() if f == field), None)
            amount = None
            if col is not None and col < len(row):
                amount, _ = _parse_amount_value(row[col])
            money_values[field] = str(amount) if amount is not None else ''

        date_col = next((i for i, f in col_map.items() if f == 'line_date'), None)
        line_date = None
        line_date_raw = ''
        if date_col is not None and date_col < len(row):
            line_date, line_date_raw = _parse_date_value(row[date_col])

        has_content = particulars or explanation or pcv or line_date or line_date_raw or any(money_values.values())
        if not has_content:
            continue

        lines.append({
            'line_date': line_date.isoformat() if line_date else '',
            'line_date_raw': line_date_raw,
            'particulars': particulars,
            'explanation': explanation,
            'tin': record.get('tin') or '',
            'pcv_number': pcv,
            **money_values,
        })

    if not found_total and lines:
        total_cash = sum(
            (Decimal(line['cash_in_bank']) for line in lines if line.get('cash_in_bank')),
            Decimal('0'),
        ).quantize(Decimal('0.01'))

    return {
        'lines': lines,
        'total_cash_in_bank': total_cash,
        'source_filename': path.name,
    }
