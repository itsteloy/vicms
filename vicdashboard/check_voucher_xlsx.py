"""Parse monthly check-voucher Excel workbooks into structured voucher data."""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
PKGREL_NS = {'p': 'http://schemas.openxmlformats.org/package/2006/relationships'}
WBREL_ID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'

MONEY_FIELDS = (
    'purchases',
    'expenses',
    'commission',
    'contributions',
    'misc',
    'payment',
    'salaries',
)

HEADER_ALIASES = {
    'date': 'voucher_date',
    'cv no': 'cv_number',
    'cv no:': 'cv_number',
    'cv no.': 'cv_number',
    'issued to': 'payee',
    'issued to:': 'payee',
    'payment for': 'payment_for',
    'payment for:': 'payment_for',
    'amount': 'check_amount',
    'purchases': 'purchases',
    'expenses': 'expenses',
    'commission': 'commission',
    'contributions': 'contributions',
    'misc': 'misc',
    'payment': 'payment',
    'salaries': 'salaries',
    'salaries and wages': 'salaries',
    'check date': 'check_date',
    'check date:': 'check_date',
    'bank': 'bank',
    'check no': 'check_number',
    'check no:': 'check_number',
    'check no.': 'check_number',
    'company': 'company',
    'company:': 'company',
    'liquidation status': 'liquidation_status',
    'liquidation status:': 'liquidation_status',
    'withholding tax': 'withholding_tax',
    'withholding tax:': 'withholding_tax',
    'less withholding tax': 'withholding_tax',
    'withholding': 'withholding_tax',
}


def _normalize_header(value: Any) -> str:
    text = re.sub(r'\s+', ' ', str(value or '').strip().lower())
    # keep trailing '.' and ':' variants mapped via aliases; also try stripped form
    return text


def _header_key(value: Any) -> str | None:
    normalized = _normalize_header(value)
    if normalized in HEADER_ALIASES:
        return HEADER_ALIASES[normalized]
    stripped = normalized.rstrip('.: ').strip()
    return HEADER_ALIASES.get(stripped)


def _col_row(cell_ref: str) -> tuple[int, int]:
    match = re.match(r'([A-Z]+)(\d+)', cell_ref)
    if not match:
        raise ValueError(f'Invalid cell reference: {cell_ref}')
    col = 0
    for ch in match.group(1):
        col = col * 26 + (ord(ch) - 64)
    return col, int(match.group(2))


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
    for fmt in ('%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d', '%d/%m/%Y',
                '%A, %B %d, %Y', '%A, %b %d, %Y', '%B %d, %Y', '%b %d, %Y'):
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


def _normalize_company(value: Any) -> str:
    text = re.sub(r'\s+', ' ', str(value or '').strip().lower())
    if 'versatec' in text:
        return 'versatec'
    if 'mdtcii' in text or ('trade' in text and 'construction' in text):
        return 'mdtcii'
    if 'metro' in text or 'mdspii' in text or 'supreme' in text or 'davao' in text:
        return 'mdspii'
    if text in ('mdspii', 'versatec', 'mdtcii'):
        return text
    return ''


def _cell_text(value: Any) -> str:
    if value is None:
        return ''
    text = str(value).strip()
    if re.fullmatch(r'\d+\.0', text):
        return text[:-2]
    return text


def _is_number(value: Any) -> bool:
    if value is None or value == '':
        return False
    try:
        Decimal(str(value).replace(',', ''))
        return True
    except (InvalidOperation, TypeError, ValueError):
        return False


def _read_xlsx_sheets(path: Path) -> dict[str, list[list[Any]]]:
    """Read all worksheet XML files and return sheet name -> rows."""
    with zipfile.ZipFile(path) as zf:
        shared: list[str] = []
        if 'xl/sharedStrings.xml' in zf.namelist():
            shared_root = ET.fromstring(zf.read('xl/sharedStrings.xml'))
            for si in shared_root.findall('m:si', NS):
                texts = [t.text or '' for t in si.findall('.//m:t', NS)]
                shared.append(''.join(texts))

        workbook = ET.fromstring(zf.read('xl/workbook.xml'))
        relationships = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
        rel_targets = {
            rel.get('Id'): rel.get('Target')
            for rel in relationships.findall('p:Relationship', PKGREL_NS)
        }

        sheets: dict[str, list[list[Any]]] = {}
        for sheet in workbook.findall('.//m:sheet', NS):
            name = sheet.get('name')
            rel_id = sheet.get(WBREL_ID)
            target = rel_targets.get(rel_id, '')
            if not name or not target:
                continue
            sheet_path = 'xl/' + target.lstrip('/')
            sheet_root = ET.fromstring(zf.read(sheet_path))
            cells: dict[int, dict[int, Any]] = {}
            for cell in sheet_root.findall('.//m:c', NS):
                ref = cell.get('r')
                if not ref:
                    continue
                col, row = _col_row(ref)
                value_el = cell.find('m:v', NS)
                if cell.get('t') == 's':
                    value: Any = shared[int(value_el.text)] if value_el is not None and value_el.text is not None else ''
                elif cell.get('t') == 'inlineStr':
                    value = ''.join(t.text or '' for t in cell.findall('.//m:t', NS))
                elif value_el is not None and value_el.text is not None:
                    value = value_el.text
                else:
                    value = ''
                cells.setdefault(row, {})[col] = value

            if not cells:
                continue
            max_row = max(cells)
            max_col = max(max(row.keys()) for row in cells.values())
            rows = []
            for row_num in range(1, max_row + 1):
                rows.append([cells.get(row_num, {}).get(col, '') for col in range(1, max_col + 1)])
            sheets[name] = rows

    return sheets


def _rows_by_col(rows: list[list[Any]]) -> dict[int, dict[int, str]]:
    """Convert row-oriented rows to column-indexed rows for label lookup."""
    result: dict[int, dict[int, str]] = {}
    for row_idx, row in enumerate(rows):
        result[row_idx] = {}
        for col_idx, value in enumerate(row):
            if str(value).strip():
                result[row_idx][col_idx] = str(value).strip()
    return result


def _find_label(rows_by_col: dict[int, dict[int, str]], label: str) -> tuple[int, int] | None:
    needle = label.lower()
    for row_idx, cells in rows_by_col.items():
        for col_idx, value in cells.items():
            if needle in value.lower():
                return row_idx, col_idx
    return None


def _find_bank_label(rows_by_col: dict[int, dict[int, str]]) -> tuple[int, int] | None:
    for row_idx, cells in rows_by_col.items():
        for col_idx, value in cells.items():
            normalized = value.strip().lower()
            if normalized.startswith('bank') and 'cash in bank' not in normalized:
                return row_idx, col_idx
    return None


def _value_after(
    rows_by_col: dict[int, dict[int, str]],
    row_idx: int,
    col_idx: int,
    *,
    numeric: bool = False,
    text: bool = False,
) -> tuple[int, int, str] | None:
    """Find the first value after a cell, scanning right then down."""
    max_col = max((max(cells.keys(), default=-1) + 1 for cells in rows_by_col.values()), default=0)
    for row in range(row_idx, max(rows_by_col.keys(), default=-1) + 1):
        for col in range(col_idx + 1, max_col):
            value = rows_by_col.get(row, {}).get(col, '')
            if numeric and _is_number(value):
                return row, col, str(value)
            if text and not numeric and str(value).strip():
                return row, col, str(value)
    return None


def _first_text_after(
    rows_by_col: dict[int, dict[int, str]], row_idx: int, col_idx: int
) -> tuple[int, int, str] | None:
    return _value_after(rows_by_col, row_idx, col_idx, text=True)


def _first_numeric_after(
    rows_by_col: dict[int, dict[int, str]], row_idx: int, col_idx: int
) -> tuple[int, int, str] | None:
    return _value_after(rows_by_col, row_idx, col_idx, numeric=True)


_LABEL_WORDS = (
    'payee', 'debit', 'credit', 'totals', 'cash in bank', 'payment for',
    'received from', 'received by', 'check amount', 'check no', 'cheque no',
    'bank', 'prepared by', 'checked by', 'approved by',
    'withholding', 'withheld', 'w/tax', 'wtax', 'ewt',
)


def _looks_like_label(text: str) -> bool:
    lowered = (text or '').strip().lower()
    if not lowered:
        return True
    if set(lowered) <= {'_', '-', ' '}:
        return True
    return any(word in lowered for word in _LABEL_WORDS)


def _text_on_same_row(
    rows_by_col: dict[int, dict[int, str]], row_idx: int, col_idx: int
) -> tuple[int, int, str] | None:
    cells = rows_by_col.get(row_idx, {})
    if not cells:
        return None
    for col in sorted(cells):
        if col <= col_idx:
            continue
        value = str(cells[col]).strip()
        if not value:
            continue
        if _looks_like_label(value) and ':' not in value:
            # label-like cells (e.g. "BANK:", "Received by:") are not values
            # unless they carry an inline value after a colon.
            continue
        if set(value) <= {'_', '-', ' '}:
            continue
        return row_idx, col, value
    return None


def _numeric_on_same_row(
    rows_by_col: dict[int, dict[int, str]], row_idx: int, col_idx: int
) -> tuple[int, int, str] | None:
    cells = rows_by_col.get(row_idx, {})
    if not cells:
        return None
    for col in sorted(cells):
        if col <= col_idx:
            continue
        value = str(cells[col]).strip()
        if _is_number(value):
            return row_idx, col, value
    return None


def _clean_bank_value(text: str) -> str:
    cleaned = (text or '').strip()
    if not cleaned or set(cleaned) <= {'_', '-', ' '}:
        return ''
    upper = cleaned.upper()
    if 'BANK' in upper and ':' in cleaned:
        # "BANK: MBTC/PBB/BDO" -> take the part after colon if present
        after = cleaned.split(':', 1)[1].strip()
        if after and set(after) != {'_'}:
            return after
        return ''
    if _looks_like_label(cleaned):
        return ''
    return cleaned


def _clean_check_number(text: str) -> str:
    cleaned = (text or '').strip()
    if not cleaned or set(cleaned) <= {'_', '-', ' '}:
        return ''
    upper = cleaned.upper()
    if 'BANK' in upper or 'RECEIVED' in upper or 'MDSPII' in upper:
        return ''
    if '//' in cleaned:
        # payee names like "ROY MIRANDA // ..." leaked from scanning down
        return ''
    if _looks_like_label(cleaned):
        return ''
    return cleaned


def _extract_cv_number(text: str) -> str:
    match = re.search(r'(\d{4}-M-\d+)', text, flags=re.IGNORECASE)
    return match.group(1) if match else ''


_WITHHOLDING_WORDS = ('withholding', 'withheld', 'w/tax', 'wtax', 'ewt')


def _is_withholding_description(description: str) -> bool:
    lowered = (description or '').strip().lower()
    return any(word in lowered for word in _WITHHOLDING_WORDS)


def _quantize_amount(value: str) -> str | None:
    try:
        return str(Decimal(str(value).replace(',', '')).quantize(Decimal('0.01')))
    except Exception:
        return None


def _collect_voucher_body_row(cells, text_cells, lines, credit_lines, debit_col, credit_col, last_side):
    """Attribute one body-row amount to the DEBIT or CREDIT column.

    Rows whose description is a sheet label (TOTALS, CASH IN BANK, …) or a
    withholding row are skipped — the withholding detector handles those.
    Returns the side written ('debit'/'credit') or the unchanged last_side
    when nothing was written.
    """
    if not text_cells:
        return last_side
    _desc_col, description = max(text_cells, key=lambda item: item[0])
    if _looks_like_label(description) or _is_withholding_description(description):
        return last_side
    debit_raw = cells.get(debit_col, '')
    credit_raw = cells.get(credit_col, '')
    debit_value = _quantize_amount(debit_raw) if _is_number(debit_raw) else None
    credit_value = _quantize_amount(credit_raw) if _is_number(credit_raw) else None
    if debit_value is None and credit_value is None:
        # Amount not aligned under either header (merged/offset cells):
        # fall back to the legacy rule so the amount is never dropped.
        legacy_cells = [
            (col, str(cells[col]).strip())
            for col in sorted(cells)
            if col in (3, 4, 5, 6) and _is_number(cells[col])
        ]
        legacy_pick = next(
            (cell for cell in legacy_cells if cell[0] > _desc_col),
            legacy_cells[0] if legacy_cells else None,
        )
        if legacy_pick is not None:
            legacy_value = _quantize_amount(legacy_pick[1])
            if legacy_value is not None:
                lines.append({'description': description, 'debit_amount': legacy_value})
                return 'debit'
        # Continuation line (e.g. "BAROBO PROJECT" under cash advance):
        # fold into the most recently written side instead of creating
        # an empty-amount row.
        target = credit_lines if last_side == 'credit' and credit_lines else (lines or credit_lines)
        if description and target:
            prev = target[-1]
            if prev.get('description') and description not in prev['description']:
                prev['description'] = f"{prev['description']} ({description})"
        return last_side
    if debit_value is not None:
        lines.append({'description': description, 'debit_amount': debit_value})
        last_side = 'debit'
    if credit_value is not None:
        credit_lines.append({'description': description, 'credit_amount': credit_value})
        last_side = 'credit'
    return last_side


def _parse_voucher_sheet(rows: list[list[Any]], cv_number: str) -> dict[str, Any]:
    rows_by_col = _rows_by_col(rows)

    cvno_label = _find_label(rows_by_col, 'CVNO')
    cvno = ''
    if cvno_label:
        row_idx, col_idx = cvno_label
        found = _value_after(rows_by_col, row_idx, col_idx, text=True)
        if found:
            cvno = _extract_cv_number(str(found[2]))
        if not cvno:
            cvno = _extract_cv_number(rows_by_col.get(row_idx, {}).get(col_idx, ''))

    date_label = _find_label(rows_by_col, 'DATE')
    date_value = ''
    if date_label:
        found = _numeric_on_same_row(rows_by_col, date_label[0], date_label[1])
        if found:
            date_value = str(found[2])
        else:
            # Text-formatted dates (e.g. "Wednesday, January 14, 2026").
            text_found = _text_on_same_row(rows_by_col, date_label[0], date_label[1])
            if text_found and _parse_date_value(str(text_found[2]))[0] is not None:
                date_value = str(text_found[2])
            else:
                scanned = _first_numeric_after(rows_by_col, date_label[0], date_label[1])
                if scanned:
                    date_value = str(scanned[2])
    voucher_date, _ = _parse_date_value(date_value)

    payee_label = _find_label(rows_by_col, 'PAYEE')
    payee = ''
    if payee_label:
        found = _text_on_same_row(rows_by_col, payee_label[0], payee_label[1])
        if not found:
            found = _first_text_after(rows_by_col, payee_label[0], payee_label[1])
        if found:
            candidate = str(found[2]).strip()
            if not _looks_like_label(candidate):
                payee = candidate

    debit_label = _find_label(rows_by_col, 'DEBIT')
    credit_label = _find_label(rows_by_col, 'CREDIT')
    if credit_label and (not debit_label or credit_label[0] != debit_label[0]):
        # Only trust a CREDIT header sitting on the same header row as DEBIT;
        # otherwise fall back to debit-only parsing to avoid misclassification.
        credit_label = None
    cash_bank_label = _find_label(rows_by_col, 'CASH IN BANK')
    totals_label = _find_label(rows_by_col, 'TOTALS')
    withholding_label_pos = (
        _find_label(rows_by_col, 'WITHHOLDING')
        or _find_label(rows_by_col, 'WITHHELD')
        or _find_label(rows_by_col, 'W/TAX')
        or _find_label(rows_by_col, 'EWT')
    )
    lines: list[dict[str, Any]] = []
    credit_lines: list[dict[str, Any]] = []
    candidates = [
        pos[0] for pos in (withholding_label_pos, cash_bank_label, totals_label) if pos
    ]
    debit_end = min(candidates) if candidates else 0
    if debit_label and debit_end and debit_end > debit_label[0]:
        debit_col = debit_label[1]
        credit_col = credit_label[1] if credit_label else None
        last_side = 'debit'
        for row_idx in range(debit_label[0] + 1, debit_end):
            cells = rows_by_col.get(row_idx, {})
            if not cells:
                continue
            # Only columns A-C hold descriptions and D-E hold amounts.
            # Columns H-K hold side notes (counter receipts, PO refs) — ignore them.
            text_cells = [
                (col, str(value).strip())
                for col, value in cells.items()
                if col <= 2 and not _is_number(value) and str(value).strip()
            ]
            if credit_col is not None:
                last_side = _collect_voucher_body_row(
                    cells, text_cells, lines, credit_lines,
                    debit_col, credit_col, last_side,
                )
                continue
            numeric_cells = [
                (col, str(value).strip())
                for col, value in cells.items()
                if col in (3, 4) and _is_number(value)
            ]
            if not text_cells:
                continue
            desc_col, description = max(text_cells, key=lambda item: item[0])
            if _looks_like_label(description):
                continue
            amount_cell = next(
                (cell for cell in numeric_cells if cell[0] > desc_col),
                None,
            )
            if not amount_cell and numeric_cells:
                amount_cell = numeric_cells[0]
            if not amount_cell:
                # Continuation line (e.g. "BAROBO PROJECT" under cash advance):
                # fold into previous line instead of creating an empty-amount row.
                if lines and description:
                    prev = lines[-1]
                    if prev.get('description') and description not in prev['description']:
                        prev['description'] = f"{prev['description']} ({description})"
                continue
            try:
                amount_value = str(Decimal(str(amount_cell[1]).replace(',', '')).quantize(Decimal('0.01')))
            except Exception:
                continue
            lines.append({
                'description': description,
                'debit_amount': amount_value,
            })

    totals_debit = Decimal('0')
    totals_credit = Decimal('0')
    if totals_label:
        numeric_after = []
        for cell in rows_by_col.get(totals_label[0], {}):
            value = rows_by_col[totals_label[0]][cell]
            if cell > totals_label[1] and _is_number(value):
                numeric_after.append((cell, value))
        numeric_after.sort(key=lambda item: item[0])
        if numeric_after:
            totals_debit = Decimal(numeric_after[0][1]).quantize(Decimal('0.01'))
        if len(numeric_after) > 1:
            totals_credit = Decimal(numeric_after[1][1]).quantize(Decimal('0.01'))

    withholding_tax = Decimal('0')
    withholding_label_text = 'WITHHOLDING TAX'
    if withholding_label_pos:
        raw_label = str(
            rows_by_col.get(withholding_label_pos[0], {}).get(withholding_label_pos[1], '')
        ).strip()
        if raw_label:
            withholding_label_text = re.sub(r'\s+', ' ', raw_label).upper()[:120]
        found = _numeric_on_same_row(rows_by_col, withholding_label_pos[0], withholding_label_pos[1])
        if not found:
            found = _first_numeric_after(rows_by_col, withholding_label_pos[0], withholding_label_pos[1])
            # Avoid picking up CASH IN BANK / TOTALS figures when scanning down.
            if found and found[0] != withholding_label_pos[0]:
                cash_row = cash_bank_label[0] if cash_bank_label else None
                totals_row = totals_label[0] if totals_label else None
                if (cash_row is not None and found[0] >= cash_row) or (
                    totals_row is not None and found[0] >= totals_row
                ):
                    found = None
        if found:
            try:
                withholding_tax = Decimal(str(found[2]).replace(',', '')).quantize(Decimal('0.01'))
            except Exception:
                withholding_tax = Decimal('0')

    cash_in_bank = Decimal('0')
    if cash_bank_label:
        found = _numeric_on_same_row(rows_by_col, cash_bank_label[0], cash_bank_label[1])
        if not found:
            found = _first_numeric_after(rows_by_col, cash_bank_label[0], cash_bank_label[1])
        if found:
            try:
                cash_in_bank = Decimal(str(found[2]).replace(',', '')).quantize(Decimal('0.01'))
            except Exception:
                cash_in_bank = Decimal('0')
    if cash_in_bank == Decimal('0') and totals_credit and withholding_tax == Decimal('0'):
        cash_in_bank = totals_credit
    if cash_in_bank == Decimal('0') and totals_debit and withholding_tax:
        # total debit - withholding tax = CASH IN BANK
        cash_in_bank = (totals_debit - withholding_tax).quantize(Decimal('0.01'))

    payment_for = ''
    payment_label = _find_label(rows_by_col, 'PAYMENT FOR')
    if payment_label:
        # Payment-for text lives in column A in the rows below the label.
        for row_idx in range(payment_label[0] + 1, min(max(rows_by_col.keys(), default=0) + 1, payment_label[0] + 6)):
            candidate = str(rows_by_col.get(row_idx, {}).get(0, '')).strip()
            if not candidate or _looks_like_label(candidate):
                continue
            payment_for = candidate
            break
        if not payment_for:
            found = _text_on_same_row(rows_by_col, payment_label[0], payment_label[1])
            if found and not _looks_like_label(str(found[2])):
                payment_for = str(found[2]).strip()

    check_amount = Decimal('0')
    check_amount_label = _find_label(rows_by_col, 'CHECK AMOUNT')
    if check_amount_label:
        found = _numeric_on_same_row(rows_by_col, check_amount_label[0], check_amount_label[1])
        if not found:
            found = _first_numeric_after(rows_by_col, check_amount_label[0], check_amount_label[1])
        if found:
            try:
                check_amount = Decimal(str(found[2]).replace(',', '')).quantize(Decimal('0.01'))
            except Exception:
                check_amount = Decimal('0')
    if check_amount == Decimal('0') and totals_credit:
        check_amount = totals_credit
    if check_amount == Decimal('0'):
        check_amount = cash_in_bank
    if withholding_tax > Decimal('0') and cash_in_bank > Decimal('0'):
        # Check Amount follows CASH IN BANK (net of withholding), not the debit total.
        if check_amount == totals_credit or check_amount == totals_debit:
            check_amount = cash_in_bank

    check_number = ''
    check_no_label = _find_label(rows_by_col, 'CHECK NO') or _find_label(rows_by_col, 'CHEQUE NO')
    if check_no_label:
        label_text = str(rows_by_col.get(check_no_label[0], {}).get(check_no_label[1], ''))
        if ':' in label_text:
            after = label_text.split(':', 1)[1].strip()
            check_number = _clean_check_number(after)
        if not check_number:
            found = _text_on_same_row(rows_by_col, check_no_label[0], check_no_label[1])
            if found:
                check_number = _clean_check_number(str(found[2]))

    bank = ''
    bank_label = _find_bank_label(rows_by_col)
    if bank_label:
        label_text = str(rows_by_col.get(bank_label[0], {}).get(bank_label[1], ''))
        if 'BANK:' in label_text.upper():
            bank = _clean_bank_value(label_text.split(':', 1)[1])
            if not bank:
                # label is just "BANK:" with value in the next cell
                found = _text_on_same_row(rows_by_col, bank_label[0], bank_label[1])
                if found:
                    bank = _clean_bank_value(str(found[2]))
        else:
            # e.g. "BANK:RCBC/MBTC/BDO" stored across label + value cells
            bank = _clean_bank_value(label_text)
            if not bank:
                found = _text_on_same_row(rows_by_col, bank_label[0], bank_label[1])
                if found:
                    bank = _clean_bank_value(str(found[2]))

    received_by = ''
    received_by_label = _find_label(rows_by_col, 'RECEIVED BY')
    if received_by_label:
        found = _text_on_same_row(rows_by_col, received_by_label[0], received_by_label[1])
        if found:
            candidate = str(found[2]).strip()
            if candidate and set(candidate) != {'_'} and not _looks_like_label(candidate):
                received_by = candidate

    signatories = ['', '', '', '']
    signatory_row = (
        _find_label(rows_by_col, 'PREPARED BY')
        or _find_label(rows_by_col, 'CHECKED BY')
        or _find_label(rows_by_col, 'APPROVED BY')
    )
    if signatory_row:
        for row_idx in range(signatory_row[0] + 1, min(len(rows_by_col), signatory_row[0] + 6)):
            cells = rows_by_col.get(row_idx, {})
            if cells:
                text_values = [str(value).strip() for value in cells.values() if str(value).strip()]
                if text_values:
                    name_text = text_values[0]
                    parts = re.split(r'\s{2,}', name_text)
                    if len(parts) >= 4:
                        signatories = [part.strip() for part in parts[:4]]
                    break

    return {
        'cv_number': cv_number or cvno,
        'company': 'mdspii',
        'voucher_date': voucher_date.isoformat() if voucher_date else '',
        'payee': payee,
        'payment_for': payment_for,
        'check_amount': str(check_amount),
        'cash_in_bank': str(cash_in_bank),
        'withholding_tax': str(withholding_tax),
        'withholding_label': withholding_label_text,
        'bank': bank,
        'check_number': check_number,
        'received_by': received_by,
        'signatory_prepared': signatories[0],
        'signatory_checked': signatories[1],
        'signatory_approved': signatories[2],
        'signatory_approver': signatories[3],
        'lines': lines,
        'credit_lines': credit_lines,
        'purchases': '',
        'expenses': '',
        'commission': '',
        'contributions': '',
        'misc': '',
        'payment': '',
        'salaries': '',
    }


def _parse_monitoring_sheet(rows: list[list[Any]], source_filename: str) -> list[dict[str, Any]]:
    if not rows:
        return []
    header_row = rows[0]
    col_map: dict[int, str] = {}
    for index, header in enumerate(header_row):
        key = _header_key(header)
        if key:
            col_map[index] = key

    vouchers: list[dict[str, Any]] = []
    for row in rows[1:]:
        if not row:
            continue
        cv_number = ''
        for col_idx, field in col_map.items():
            if field == 'cv_number':
                cv_number = _cell_text(row[col_idx] if col_idx < len(row) else '').strip()
        if not cv_number:
            continue
        if not re.fullmatch(r'\d{4}-M-\d+', cv_number):
            continue

        record: dict[str, Any] = {
            'cv_number': cv_number,
            'company': 'mdspii',
            'voucher_date': '',
            'payee': '',
            'payment_for': '',
            'check_amount': '',
            'cash_in_bank': '',
            'withholding_tax': '',
            'withholding_label': '',
            'bank': '',
            'check_number': '',
            'received_by': '',
            'signatory_prepared': '',
            'signatory_checked': '',
            'signatory_approved': '',
            'signatory_approver': '',
            'lines': [],
            'purchases': '',
            'expenses': '',
            'commission': '',
            'contributions': '',
            'misc': '',
            'payment': '',
            'salaries': '',
            'liquidation_status': '',
            'source_filename': source_filename,
        }
        for col_idx, field in col_map.items():
            value = row[col_idx] if col_idx < len(row) else ''
            if field == 'company':
                normalized = _normalize_company(value)
                record['company'] = normalized or 'mdspii'
                continue
            if field in MONEY_FIELDS or field in {'check_amount', 'cash_in_bank', 'withholding_tax'}:
                parsed, _ = _parse_amount_value(value)
                record[field] = str(parsed.quantize(Decimal('0.01'))) if parsed is not None else ''
                continue
            if field in {'voucher_date', 'check_date'}:
                parsed_date, _ = _parse_date_value(value)
                record[field] = parsed_date.isoformat() if parsed_date else ''
                continue
            record[field] = _cell_text(value)

        vouchers.append(record)

    return vouchers


def parse_check_voucher_xlsx(path: Path) -> dict[str, Any]:
    sheets = _read_xlsx_sheets(path)
    monitoring_rows = sheets.get('CV MONITORING') or []
    monitoring_vouchers = _parse_monitoring_sheet(monitoring_rows, path.name)

    vouchers_by_number: dict[str, dict[str, Any]] = {
        voucher['cv_number']: voucher for voucher in monitoring_vouchers
    }

    for sheet_name, rows in sheets.items():
        match = re.fullmatch(r'(\d+)', sheet_name.strip())
        if not match or sheet_name.strip() == 'CV MONITORING':
            continue
        sheet_number = match.group(1)
        cv_number = f'2026-M-{sheet_number}'
        parsed = _parse_voucher_sheet(rows, cv_number)
        if parsed['cv_number']:
            vouchers_by_number[parsed['cv_number']] = parsed

    vouchers = []
    for voucher in vouchers_by_number.values():
        monitoring = next(
            (item for item in monitoring_vouchers if item['cv_number'] == voucher['cv_number']),
            None,
        )
        if monitoring:
            for key, value in monitoring.items():
                if key in {'cv_number', 'lines'}:
                    continue
                if value not in (None, ''):
                    # Monitoring is authoritative for header/category fields.
                    # Voucher sheets supply debit lines + signatories.
                    if key == 'company':
                        voucher[key] = _normalize_company(value) or voucher.get(key) or 'mdspii'
                    elif key in {'bank', 'check_number', 'received_by', 'payee', 'payment_for'}:
                        voucher[key] = value
                    elif key in MONEY_FIELDS or key in {'check_amount', 'cash_in_bank', 'withholding_tax', 'withholding_label', 'voucher_date', 'check_date', 'source_filename'}:
                        voucher[key] = value
                    elif not voucher.get(key):
                        voucher[key] = value
            # Monitoring AMOUNT doubles as check total when voucher totals are zero.
            if monitoring.get('check_amount') and voucher.get('check_amount') in (None, '', '0', '0.00'):
                voucher['check_amount'] = monitoring['check_amount']
            if monitoring.get('check_amount') and voucher.get('cash_in_bank') in (None, '', '0', '0.00'):
                voucher['cash_in_bank'] = monitoring['check_amount']
        else:
            voucher.setdefault('source_filename', path.name)
        for field in MONEY_FIELDS:
            voucher.setdefault(field, '')
        voucher.setdefault('company', 'mdspii')
        voucher.setdefault('check_date', '')
        voucher.setdefault('source_filename', path.name)
        vouchers.append(voucher)

    vouchers.sort(key=lambda item: item['cv_number'])
    return {
        'vouchers': vouchers,
        'count': len(vouchers),
        'source_filename': path.name,
    }
