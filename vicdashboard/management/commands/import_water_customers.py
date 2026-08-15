"""Import water customers and meter readings from CUSTOMERS.xlsx."""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from vicdashboard.models import WaterCustomer, WaterMeterReading, WaterZone
from vicdashboard.views import _water_bill_from_reading

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
METER_PLACEHOLDER = '—'
BILLING_PERIOD = '2026-08'
READING_DATE = date(2026, 8, 28)


def _col_row(cell_ref: str) -> tuple[int, int]:
    match = re.match(r'([A-Z]+)(\d+)', cell_ref)
    if not match:
        raise ValueError(f'Invalid cell reference: {cell_ref}')
    col = 0
    for ch in match.group(1):
        col = col * 26 + (ord(ch) - 64)
    return col, int(match.group(2))


def read_xlsx_rows(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as zf:
        shared_root = ET.fromstring(zf.read('xl/sharedStrings.xml'))
        shared = []
        for si in shared_root.findall('m:si', NS):
            texts = [t.text or '' for t in si.findall('.//m:t', NS)]
            shared.append(''.join(texts))

        sheet = ET.fromstring(zf.read('xl/worksheets/sheet1.xml'))
        cells: dict[int, dict[int, str]] = {}
        for cell in sheet.findall('.//m:c', NS):
            ref = cell.get('r')
            if not ref:
                continue
            col, row = _col_row(ref)
            value_el = cell.find('m:v', NS)
            if value_el is None or value_el.text is None:
                val = ''
            elif cell.get('t') == 's':
                val = shared[int(value_el.text)]
            else:
                val = value_el.text
            cells.setdefault(row, {})[col] = val

    if not cells:
        return []

    header_row = cells[min(cells)]
    headers = {col: str(header_row.get(col, '')).strip().upper() for col in header_row}
    col_zone = next((c for c, h in headers.items() if h == 'ZONE'), 1)
    col_meter = next((c for c, h in headers.items() if 'METER' in h), 2)
    col_name = next((c for c, h in headers.items() if 'CUSTOMER' in h or 'NAME' in h), 3)
    col_prev = next((c for c, h in headers.items() if h == 'PREVIOUS'), 4)
    col_pres = next((c for c, h in headers.items() if h == 'PRESENT'), 5)

    rows = []
    for row_num in range(min(cells) + 1, max(cells) + 1):
        cols = cells.get(row_num, {})
        rows.append({
            'excel_row': row_num,
            'zone': str(cols.get(col_zone, '') or '').strip(),
            'meter': str(cols.get(col_meter, '') or '').strip(),
            'name': str(cols.get(col_name, '') or '').strip(),
            'previous': str(cols.get(col_prev, '') or '').strip(),
            'present': str(cols.get(col_pres, '') or '').strip(),
        })
    return rows


def split_name(raw: str) -> tuple[str, str]:
    name = raw.strip()
    if ',' in name:
        last, first = name.split(',', 1)
        return last.strip(), first.strip()
    return name, ''


def parse_reading(value: str) -> int:
    """Missing or non-numeric readings import as 0 so every customer still gets a reading."""
    text = (value or '').strip().replace(',', '')
    if not text or text in {METER_PLACEHOLDER, '-', '–'}:
        return 0
    try:
        number = float(text)
    except ValueError:
        return 0
    parsed = int(number)
    return parsed if parsed >= 0 else 0


def normalize_meter(raw: str) -> str:
    meter = (raw or '').strip()
    if not meter or meter in {'-', '–'}:
        return METER_PLACEHOLDER
    if meter == METER_PLACEHOLDER:
        return METER_PLACEHOLDER
    return meter.upper()


class Command(BaseCommand):
    help = 'Import water customers and August 2026 readings from CUSTOMERS.xlsx'

    def add_arguments(self, parser):
        parser.add_argument('xlsx_path', nargs='?', default='media/hr_documents/CUSTOMERS.xlsx')

    def handle(self, *args, **options):
        path = Path(options['xlsx_path'])
        if not path.is_file():
            raise CommandError(f'File not found: {path}')

        source_rows = read_xlsx_rows(path)
        if not source_rows:
            raise CommandError('No data rows found in the spreadsheet.')

        existing_meters = set(
            WaterCustomer.objects.exclude(meter_number=METER_PLACEHOLDER)
            .values_list('meter_number', flat=True)
        )

        created_customers = 0
        created_readings = 0
        created_bills = 0
        skipped_meter_conflict = 0
        existing_customers = 0
        meter_conflicts: list[str] = []

        with transaction.atomic():
            for row in source_rows:
                name = row['name'].strip() or 'NATIVIDAD ARGUELLES'

                meter = normalize_meter(row['meter'])

                zone = None
                zone_name = row['zone'].strip().upper()
                if zone_name:
                    zone, _ = WaterZone.objects.get_or_create(name=zone_name)

                last_name, first_name = split_name(name)
                last_name = last_name.strip().upper()
                first_name = first_name.strip().upper()
                customer = WaterCustomer.objects.filter(
                    last_name=last_name,
                    first_name=first_name,
                    zone=zone,
                ).first()
                if not customer and meter != METER_PLACEHOLDER:
                    customer = WaterCustomer.objects.filter(meter_number=meter).first()

                if customer:
                    existing_customers += 1
                else:
                    if meter != METER_PLACEHOLDER and meter in existing_meters:
                        skipped_meter_conflict += 1
                        meter_conflicts.append(f"row {row['excel_row']} {name} meter {meter}")
                        self.stdout.write(f"Skip row {row['excel_row']}: meter {meter} already exists.")
                        continue
                    customer = WaterCustomer.objects.create(
                        first_name=first_name,
                        last_name=last_name,
                        zone=zone,
                        meter_number=meter,
                        customer_type='residential',
                        connection_status='active',
                        installment_balance=0,
                    )
                    created_customers += 1
                    if meter != METER_PLACEHOLDER:
                        existing_meters.add(meter)

                previous = parse_reading(row['previous'])
                present = parse_reading(row['present'])
                reading, reading_created = WaterMeterReading.objects.get_or_create(
                    customer=customer,
                    billing_period=BILLING_PERIOD,
                    defaults={
                        'reading_date': READING_DATE,
                        'previous_reading': previous,
                        'current_reading': present,
                    },
                )
                if reading_created:
                    created_readings += 1

                _bill, bill_created = _water_bill_from_reading(reading)
                if bill_created:
                    created_bills += 1

        self.stdout.write(self.style.SUCCESS(
            f'Imported {created_customers} customers, {created_readings} readings, '
            f'and {created_bills} bills '
            f'(period {BILLING_PERIOD}, date {READING_DATE.isoformat()}).'
        ))
        self.stdout.write(
            f'Already present: {existing_customers}; meter conflicts: {skipped_meter_conflict}.'
        )
        for item in meter_conflicts:
            self.stdout.write(f'  {item}')
