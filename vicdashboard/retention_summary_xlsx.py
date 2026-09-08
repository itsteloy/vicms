"""Parse Retention Summary Excel workbooks into structured report data."""

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

HEADER_ALIASES = {
    'date': 'delivery_date',
    'date of delivery': 'delivery_date',
    'delivery date': 'delivery_date',
    'client': 'client_name',
    'client name': 'client_name',
    'customer': 'client_name',
    'customer name': 'client_name',
    'trxn amount': 'trxn_amount',
    'txn amount': 'trxn_amount',
    'transaction amount': 'trxn_amount',
    'percent': 'percent',
    '%': 'percent',
    'retention %': 'percent',
    'amount': 'amount',
    'retention amount': 'amount',
    'retention': 'amount',
    'remarks': 'remarks',
}


def parse_retention_summary_xlsx(path: Path) -> dict:
    rows = _read_xlsx_rows(path)
    if not rows:
        return {
            'lines': [],
            'total_trxn_amount': Decimal('0'),
            'total_retention_amount': Decimal('0'),
            'source_filename': path.name,
        }

    header_row = rows[0]
    col_map: dict[int, str] = {}
    for index, header in enumerate(header_row):
        key = HEADER_ALIASES.get(_normalize_header(header))
        if key:
            col_map[index] = key

    lines = []
    total_trxn = Decimal('0')
    total_retention = Decimal('0')

    for row in rows[1:]:
        if not row:
            continue
        record: dict[str, Any] = {field: '' for field in HEADER_ALIASES.values()}
        for col_index, field in col_map.items():
            value = row[col_index] if col_index < len(row) else ''
            if field in {'trxn_amount', 'amount', 'delivery_date', 'percent'}:
                continue
            record[field] = _cell_text(value)

        client = (record.get('client_name') or '').strip()
        if not client:
            continue
        upper = client.upper()
        if upper in {'GRAND TOTAL', 'TOTAL', 'TOTAL RETENTION'}:
            trxn_col = next((i for i, f in col_map.items() if f == 'trxn_amount'), None)
            amount_col = next((i for i, f in col_map.items() if f == 'amount'), None)
            if trxn_col is not None and trxn_col < len(row):
                parsed, _ = _parse_amount_value(row[trxn_col])
                if parsed is not None:
                    total_trxn = parsed.quantize(Decimal('0.01'))
            if amount_col is not None and amount_col < len(row):
                parsed, _ = _parse_amount_value(row[amount_col])
                if parsed is not None:
                    total_retention = parsed.quantize(Decimal('0.01'))
            continue

        date_col = next((i for i, f in col_map.items() if f == 'delivery_date'), None)
        delivery_date = None
        delivery_date_raw = ''
        if date_col is not None and date_col < len(row):
            delivery_date, delivery_date_raw = _parse_date_value(row[date_col])

        trxn_col = next((i for i, f in col_map.items() if f == 'trxn_amount'), None)
        trxn_amount = None
        trxn_amount_raw = ''
        if trxn_col is not None and trxn_col < len(row):
            trxn_amount, trxn_amount_raw = _parse_amount_value(row[trxn_col])

        percent_col = next((i for i, f in col_map.items() if f == 'percent'), None)
        percent = None
        if percent_col is not None and percent_col < len(row):
            percent, _ = _parse_amount_value(row[percent_col])

        amount_col = next((i for i, f in col_map.items() if f == 'amount'), None)
        amount = None
        amount_raw = ''
        if amount_col is not None and amount_col < len(row):
            amount, amount_raw = _parse_amount_value(row[amount_col])

        lines.append({
            'delivery_date': delivery_date.isoformat() if delivery_date else '',
            'delivery_date_raw': delivery_date_raw,
            'client_name': client,
            'trxn_amount': str(trxn_amount) if trxn_amount is not None else '',
            'trxn_amount_raw': trxn_amount_raw,
            'percent': str(percent) if percent is not None else '',
            'amount': str(amount) if amount is not None else '',
            'amount_raw': amount_raw,
            'remarks': record.get('remarks') or '',
            'flag_red_remarks': False,
            'flag_yellow_client': False,
            'flag_pink_row': False,
        })

    if not total_trxn and lines:
        total_trxn = sum(
            (Decimal(line['trxn_amount']) for line in lines if line['trxn_amount']),
            Decimal('0'),
        ).quantize(Decimal('0.01'))
    if not total_retention and lines:
        total_retention = sum(
            (Decimal(line['amount']) for line in lines if line['amount']),
            Decimal('0'),
        ).quantize(Decimal('0.01'))

    return {
        'lines': lines,
        'total_trxn_amount': total_trxn,
        'total_retention_amount': total_retention,
        'source_filename': path.name,
    }
