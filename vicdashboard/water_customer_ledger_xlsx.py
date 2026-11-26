"""Build the yearly customer water ledger (data + Excel workbook)."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from django.db.models import Prefetch, Q
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import WaterBill, WaterCustomer, WaterPayment, net_water_only_outstanding

MONTH_ABBR = (
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
)

TITLE_FONT = Font(name='Calibri', bold=True, size=14)
HEADER_FONT = Font(name='Calibri', bold=True, size=10, color='FFFFFF')
CELL_FONT = Font(name='Calibri', size=10)
BOLD_FONT = Font(name='Calibri', bold=True, size=10)
HEADER_FILL = PatternFill('solid', fgColor='2F5597')
GROUP_FILL = PatternFill('solid', fgColor='D9E2F3')
TOTAL_FILL = PatternFill('solid', fgColor='E7E6E6')

CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)
LEFT = Alignment(horizontal='left', vertical='center')
RIGHT = Alignment(horizontal='right', vertical='center')

THIN = Border(
    left=Side(style='thin', color='808080'),
    right=Side(style='thin', color='808080'),
    top=Side(style='thin', color='808080'),
    bottom=Side(style='thin', color='808080'),
)

MONEY_FORMAT = '#,##0.00'
BLANK = ''


def _format_money(value) -> str:
    return f'{(value or Decimal("0.00")):,.2f}'


def _month_cell_value(month: dict) -> str | None:
    parts = []
    if month['previous_reading'] is not None and month['current_reading'] is not None:
        parts.append(
            f"Rdg: {month['previous_reading']}\u2192{month['current_reading']}"
        )
    if month['has_bill']:
        parts.append(f"Cu.M: {month['consumption']}")
    if month['payment']:
        parts.append(f"Paid: {_format_money(month['payment'])}")
    return '\n'.join(parts) if parts else None


def build_water_customer_ledger(year: int, zone_id=None) -> list[dict]:
    """Return one ledger row per customer for ``year``.

    Each monthly cell holds the meter reading span (previous to current),
    cu.m consumption and the water-bill payment recorded against that month's
    bill. Payments are attributed to the bill they paid, not the date the
    payment was received. When ``zone_id`` is given, only customers in that
    zone are included.
    """
    year = int(year)
    year_prefix = f'{year}-'
    customers = WaterCustomer.objects.prefetch_related(
        Prefetch(
            'bills',
            queryset=WaterBill.objects.exclude(status='cancelled')
            .select_related('meter_reading')
            .order_by('bill_date', 'pk'),
            to_attr='ledger_bills',
        ),
        Prefetch(
            'payments',
            queryset=WaterPayment.objects.filter(
                Q(bill__billing_period__startswith=year_prefix)
                | Q(bill__isnull=True, payment_date__year=year),
                purpose=WaterPayment.PURPOSE_BILL,
            ).select_related('bill').order_by('bill__bill_date', 'payment_date', 'id'),
            to_attr='ledger_payments',
        ),
    )
    if zone_id:
        customers = customers.filter(zone_id=zone_id)
    customers = customers.order_by('last_name', 'first_name')

    rows = []
    for customer in customers:
        consumption = [0] * 12
        has_bill = [False] * 12
        previous_readings = [None] * 12
        current_readings = [None] * 12

        for bill in customer.ledger_bills:
            period = (bill.billing_period or '').strip()
            if len(period) < 7 or not period.startswith(year_prefix):
                continue
            try:
                month = int(period[5:7])
            except ValueError:
                continue
            if not 1 <= month <= 12:
                continue
            consumption[month - 1] += int(bill.consumption or 0)
            has_bill[month - 1] = True

            reading = getattr(bill, 'meter_reading', None)
            if reading is not None:
                if previous_readings[month - 1] is None:
                    previous_readings[month - 1] = reading.previous_reading
                current_readings[month - 1] = reading.current_reading

        payments = [Decimal('0.00')] * 12
        for payment in customer.ledger_payments:
            month = None
            if payment.bill is not None:
                period = (payment.bill.billing_period or '').strip()
                if len(period) >= 7 and period.startswith(year_prefix):
                    try:
                        billed_month = int(period[5:7])
                    except ValueError:
                        billed_month = 0
                    if 1 <= billed_month <= 12:
                        month = billed_month
            elif payment.payment_date and payment.payment_date.year == year:
                month = payment.payment_date.month
            if month is None:
                continue
            payments[month - 1] += payment.amount or Decimal('0.00')

        months = []
        for index in range(12):
            months.append({
                'has_bill': has_bill[index],
                'previous_reading': previous_readings[index],
                'current_reading': current_readings[index],
                'consumption': consumption[index],
                'payment': payments[index],
            })

        water_balance = net_water_only_outstanding(customer.ledger_bills)
        installment = (customer.installment_balance or Decimal('0.00')).quantize(Decimal('0.01'))
        total = (water_balance + installment).quantize(Decimal('0.01'))

        rows.append({
            'name': customer.display_name,
            'months': months,
            'current_water_balance': water_balance,
            'installment_balance': installment,
            'total_balance': total,
        })
    return rows


def build_water_customer_ledger_xlsx(year: int, rows: list[dict], zone_name: str | None = None) -> bytes:
    zone_label = (zone_name or '').strip()
    workbook = Workbook()
    sheet = workbook.active
    sheet_title = f'Ledger {year}'
    if zone_label:
        sheet_title = f'{sheet_title} {zone_label}'[:31]
    sheet.title = sheet_title

    last_column = 16
    sheet.merge_cells(
        start_row=1, start_column=1, end_row=1, end_column=last_column,
    )
    title_text = f'CUSTOMER WATER LEDGER - {year}'
    if zone_label:
        title_text = f'{title_text} - {zone_label}'
    title = sheet.cell(row=1, column=1, value=title_text)
    title.font = TITLE_FONT
    title.alignment = CENTER
    sheet.row_dimensions[1].height = 22

    sheet.merge_cells(start_row=2, start_column=1, end_row=3, end_column=1)
    name_header = sheet.cell(row=2, column=1, value='Name')
    sheet.merge_cells(start_row=2, start_column=2, end_row=2, end_column=13)
    group = sheet.cell(
        row=2, column=2, value='Meter Reading / C.u M / Payments per Month',
    )
    group.font = HEADER_FONT
    group.fill = HEADER_FILL
    group.alignment = CENTER

    for index, label in enumerate(MONTH_ABBR, start=2):
        cell = sheet.cell(row=3, column=index, value=label)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = THIN

    balance_headers = (
        (14, 'Current Water Bill Balance'),
        (15, 'Installment Balance'),
        (16, 'Total Balance'),
    )
    for column, label in balance_headers:
        sheet.merge_cells(start_row=2, start_column=column, end_row=3, end_column=column)
        cell = sheet.cell(row=2, column=column, value=label)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = THIN

    name_header.font = HEADER_FONT
    name_header.fill = HEADER_FILL
    name_header.alignment = CENTER
    name_header.border = THIN
    group.border = THIN

    data_start = 4
    row_index = data_start
    for row in rows:
        name_cell = sheet.cell(row=row_index, column=1, value=row['name'])
        name_cell.font = CELL_FONT
        name_cell.alignment = LEFT
        name_cell.border = THIN

        for offset, month in enumerate(row['months'], start=2):
            cell = sheet.cell(
                row=row_index, column=offset, value=_month_cell_value(month),
            )
            cell.font = CELL_FONT
            cell.alignment = CENTER
            cell.border = THIN

        if any(month['has_bill'] for month in row['months']):
            sheet.row_dimensions[row_index].height = 45

        for column, key in (
            (14, 'current_water_balance'),
            (15, 'installment_balance'),
            (16, 'total_balance'),
        ):
            cell = sheet.cell(row=row_index, column=column, value=float(row[key]))
            cell.font = CELL_FONT
            cell.alignment = RIGHT
            cell.number_format = MONEY_FORMAT
            cell.border = THIN

        row_index += 1

    if rows:
        total_current = sum((row['current_water_balance'] for row in rows), Decimal('0.00'))
        total_installment = sum((row['installment_balance'] for row in rows), Decimal('0.00'))
        total_balance = sum((row['total_balance'] for row in rows), Decimal('0.00'))

        sheet.merge_cells(start_row=row_index, start_column=1, end_row=row_index, end_column=13)
        label_cell = sheet.cell(row=row_index, column=1, value='TOTAL')
        label_cell.font = BOLD_FONT
        label_cell.fill = TOTAL_FILL
        label_cell.alignment = RIGHT
        label_cell.border = THIN

        for column, value in (
            (14, total_current),
            (15, total_installment),
            (16, total_balance),
        ):
            cell = sheet.cell(row=row_index, column=column, value=float(value))
            cell.font = BOLD_FONT
            cell.fill = TOTAL_FILL
            cell.alignment = RIGHT
            cell.number_format = MONEY_FORMAT
            cell.border = THIN

    sheet.freeze_panes = 'B4'
    sheet.column_dimensions['A'].width = 32
    for column in range(2, 14):
        sheet.column_dimensions[get_column_letter(column)].width = 14
    for column in (14, 15, 16):
        sheet.column_dimensions[get_column_letter(column)].width = 16

    sheet.page_setup.orientation = 'landscape'
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
