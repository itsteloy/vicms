"""Parse biometric punch attendance sheets (.xls SpreadsheetML or binary BIFF)."""

from __future__ import annotations

import re
from datetime import date
from xml.etree import ElementTree as ET

SS_NS = 'urn:schemas-microsoft-com:office:spreadsheet'
NS = {'ss': SS_NS}

HEADER_RE = re.compile(
    r'ID\s*:\s*(?P<id>\S+)\s+Name\s*:\s*(?P<name>.*?)\s+Dept\s*:\s*(?P<dept>.*?)\s+Shift\s*:\s*(?P<shift>\S*)\s*$',
    re.IGNORECASE,
)
TITLE_RE = re.compile(
    r'(?P<year>\d{4})\s*:\s*(?P<sm>\d{1,2})\s*/\s*(?P<sd>\d{1,2})\s*-\s*(?P<em>\d{1,2})\s*/\s*(?P<ed>\d{1,2})',
)


class AttendanceSheetParseError(ValueError):
    pass


def _ss(attr: str) -> str:
    return f'{{{SS_NS}}}{attr}'


def _cell_text(cell) -> str:
    data = cell.find('ss:Data', NS)
    if data is None or data.text is None:
        return ''
    return str(data.text).strip()


def _row_cells(row) -> list[str]:
    out: list[str] = []
    idx = 0
    for cell in row.findall('ss:Cell', NS):
        index_attr = cell.get(_ss('Index'))
        if index_attr:
            idx = int(index_attr) - 1
        while len(out) < idx:
            out.append('')
        out.append(_cell_text(cell))
        merge = cell.get(_ss('MergeAcross'))
        span = int(merge) + 1 if merge else 1
        idx += span
    return out


def _parse_period(title: str) -> tuple[int | None, date | None, date | None]:
    match = TITLE_RE.search(title or '')
    if not match:
        return None, None, None
    year = int(match.group('year'))
    start = date(year, int(match.group('sm')), int(match.group('sd')))
    end_month = int(match.group('em'))
    end_day = int(match.group('ed'))
    end_year = year if end_month >= int(match.group('sm')) else year + 1
    end = date(end_year, end_month, end_day)
    return year, start, end


def _resolve_punch_date(day: int, period_start: date | None, period_end: date | None) -> date | None:
    if not period_start or not period_end:
        return None
    cursor = period_start
    while cursor <= period_end:
        if cursor.day == day:
            return cursor
        cursor = date.fromordinal(cursor.toordinal() + 1)
    return None


def _parse_employee_header(text: str) -> dict | None:
    match = HEADER_RE.match((text or '').strip())
    if not match:
        return None
    return {
        'device_employee_id': match.group('id').strip(),
        'employee_name': match.group('name').strip(),
        'department': match.group('dept').strip(),
        'shift': match.group('shift').strip(),
    }


def split_punch_slots(text: str) -> dict[str, str]:
    """Split device punch cell into morning/afternoon in & out slots."""
    times = [part for part in str(text or '').split() if part]
    morning_in = morning_out = afternoon_in = afternoon_out = ''
    if len(times) == 1:
        morning_in = times[0]
    elif len(times) == 2:
        morning_in, afternoon_out = times[0], times[1]
    elif len(times) == 3:
        morning_in, morning_out, afternoon_out = times[0], times[1], times[2]
    elif len(times) >= 4:
        morning_in, morning_out, afternoon_in, afternoon_out = times[0], times[1], times[2], times[3]
    return {
        'morning_in': morning_in,
        'morning_out': morning_out,
        'afternoon_in': afternoon_in,
        'afternoon_out': afternoon_out,
    }


def _build_result(title: str, employees: list[dict]) -> dict:
    year, period_start, period_end = _parse_period(title)
    for emp in employees:
        for punch in emp.get('punches', []):
            day = punch.get('day')
            if day is not None:
                punch['punch_date'] = _resolve_punch_date(int(day), period_start, period_end)
            punch.update(split_punch_slots(punch.get('punch_times', '')))
    return {
        'title': title or 'Punch Sheet',
        'period_year': year,
        'period_start': period_start,
        'period_end': period_end,
        'employees': employees,
    }


def parse_spreadsheetml(raw: bytes | str) -> dict:
    if isinstance(raw, bytes):
        text = raw.decode('utf-8-sig', errors='replace')
    else:
        text = raw.lstrip('\ufeff')

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise AttendanceSheetParseError(f'Invalid SpreadsheetML XML: {exc}') from exc

    table = root.find('.//ss:Worksheet/ss:Table', NS)
    if table is None:
        raise AttendanceSheetParseError('No worksheet table found in the uploaded file.')

    rows = [_row_cells(row) for row in table.findall('ss:Row', NS)]
    if not rows:
        raise AttendanceSheetParseError('The punch sheet is empty.')

    title = next((c for c in rows[0] if c), 'Punch Sheet')
    employees: list[dict] = []
    i = 1
    while i < len(rows):
        cells = rows[i]
        header_text = next((c for c in cells if c), '')
        header = _parse_employee_header(header_text)
        if not header:
            i += 1
            continue

        day_row = rows[i + 1] if i + 1 < len(rows) else []
        punch_row = rows[i + 2] if i + 2 < len(rows) else []
        days: list[int] = []
        for cell in day_row:
            if not cell:
                continue
            try:
                days.append(int(float(cell)))
            except (TypeError, ValueError):
                continue

        punches = []
        for idx, day in enumerate(days):
            times = punch_row[idx].strip() if idx < len(punch_row) else ''
            punches.append({'day': day, 'punch_times': times, 'sort_order': idx})

        employees.append({**header, 'punches': punches})
        i += 3

    if not employees:
        raise AttendanceSheetParseError(
            'No employee punch blocks found. Expected rows like '
            '"ID:00000001  Name:...  Dept:...  Shift:..."'
        )

    return _build_result(title, employees)


def parse_binary_xls(raw: bytes) -> dict:
    try:
        import xlrd
    except ImportError as exc:
        raise AttendanceSheetParseError(
            'Binary .xls support requires the xlrd package.'
        ) from exc

    try:
        book = xlrd.open_workbook(file_contents=raw)
    except Exception as exc:  # noqa: BLE001 — surface as parse error
        raise AttendanceSheetParseError(f'Could not read binary .xls: {exc}') from exc

    sheet = book.sheet_by_index(0)

    def row_values(r: int) -> list[str]:
        vals = []
        for c in range(sheet.ncols):
            cell = sheet.cell(r, c)
            if cell.ctype == xlrd.XL_CELL_NUMBER:
                num = cell.value
                vals.append(str(int(num)) if float(num).is_integer() else str(num))
            elif cell.ctype == xlrd.XL_CELL_EMPTY:
                vals.append('')
            else:
                vals.append(str(cell.value).strip())
        return vals

    rows = [row_values(r) for r in range(sheet.nrows)]
    if not rows:
        raise AttendanceSheetParseError('The punch sheet is empty.')

    title = next((c for c in rows[0] if c), 'Punch Sheet')
    employees: list[dict] = []
    i = 1
    while i < len(rows):
        cells = rows[i]
        header_text = next((c for c in cells if c), '')
        header = _parse_employee_header(header_text)
        if not header:
            i += 1
            continue

        day_row = rows[i + 1] if i + 1 < len(rows) else []
        punch_row = rows[i + 2] if i + 2 < len(rows) else []
        days: list[int] = []
        for cell in day_row:
            if not cell:
                continue
            try:
                days.append(int(float(cell)))
            except (TypeError, ValueError):
                continue

        punches = []
        for idx, day in enumerate(days):
            times = punch_row[idx].strip() if idx < len(punch_row) else ''
            punches.append({'day': day, 'punch_times': times, 'sort_order': idx})

        employees.append({**header, 'punches': punches})
        i += 3

    if not employees:
        raise AttendanceSheetParseError('No employee punch blocks found in the binary .xls file.')

    return _build_result(title, employees)


def parse_attendance_sheet_file(uploaded_file) -> dict:
    """Parse an uploaded punch sheet file (.xls SpreadsheetML or binary)."""
    name = (getattr(uploaded_file, 'name', '') or '').lower()
    raw = uploaded_file.read()
    if hasattr(uploaded_file, 'seek'):
        try:
            uploaded_file.seek(0)
        except Exception:  # noqa: BLE001
            pass

    if not raw:
        raise AttendanceSheetParseError('Uploaded file is empty.')

    head = raw.lstrip()[:200]
    if head.startswith(b'<?xml') or head.startswith(b'\xef\xbb\xbf<?xml') or b'mso-application' in head[:500]:
        return parse_spreadsheetml(raw)

    if name.endswith('.xlsx'):
        raise AttendanceSheetParseError(
            'Excel .xlsx is not supported for punch sheets. Please upload the .xls export from the biometric device.'
        )

    # Biometric devices often label SpreadsheetML as .xls — try XML first on text-looking content
    if b'Workbook' in raw[:2000] or b'spreadsheet' in raw[:2000].lower():
        return parse_spreadsheetml(raw)

    return parse_binary_xls(raw)
