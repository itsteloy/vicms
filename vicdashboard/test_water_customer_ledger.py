from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from .models import WaterBill, WaterCustomer, WaterMeterReading, WaterPayment, WaterZone


class WaterCustomerLedgerExportTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='water-ledger-manager',
            password='test-password-123',
        )
        self.client.force_login(user)

        self.zone_north = WaterZone.objects.create(name='ZONE NORTH')
        self.zone_south = WaterZone.objects.create(name='ZONE SOUTH')

        self.customer_a = WaterCustomer.objects.create(
            account_number='WA-2026-001',
            first_name='ANA',
            last_name='ALPHA',
            meter_number='MTR-001',
            installment_balance=Decimal('300.00'),
            zone=self.zone_north,
        )
        self.customer_b = WaterCustomer.objects.create(
            account_number='WA-2026-002',
            first_name='BEN',
            last_name='BRAVO',
            meter_number='MTR-002',
            zone=self.zone_south,
        )

        self.bill_jan = WaterBill.objects.create(
            customer=self.customer_a,
            billing_period='2026-01',
            bill_date=date(2026, 1, 5),
            due_date=date(2026, 1, 20),
            consumption=10,
            rate_per_cum=Decimal('20.00'),
            amount_paid=Decimal('200.00'),
        )
        self.bill_feb = WaterBill.objects.create(
            customer=self.customer_a,
            billing_period='2026-02',
            bill_date=date(2026, 2, 5),
            due_date=date(2026, 2, 20),
            consumption=3,
            rate_per_cum=Decimal('20.00'),
        )

        WaterPayment.objects.create(
            customer=self.customer_a,
            bill=self.bill_jan,
            purpose=WaterPayment.PURPOSE_BILL,
            payment_date=date(2026, 1, 15),
            amount=Decimal('200.00'),
        )
        WaterPayment.objects.create(
            customer=self.customer_a,
            purpose=WaterPayment.PURPOSE_INSTALLATION,
            payment_date=date(2026, 1, 15),
            amount=Decimal('500.00'),
        )
        WaterPayment.objects.create(
            customer=self.customer_b,
            purpose=WaterPayment.PURPOSE_BILL,
            payment_date=date(2026, 3, 10),
            amount=Decimal('150.00'),
        )

    def _download(self, **params):
        response = self.client.get(reverse('water_customer_ledger_xlsx'), params)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        return response, load_workbook(BytesIO(response.content)).active

    def _row_for(self, sheet, name):
        for row in sheet.iter_rows(min_row=4, max_col=1):
            if row[0].value == name:
                return row[0].row
        self.fail(f'Row for {name!r} not found')

    def test_export_builds_monthly_ledger_with_balances(self):
        response, sheet = self._download(year=2026)

        self.assertIn('water_customer_ledger_2026.xlsx', response['Content-Disposition'])
        self.assertEqual(sheet['A1'].value, 'CUSTOMER WATER LEDGER - 2026')
        self.assertEqual(sheet['A2'].value, 'Name')
        self.assertEqual(sheet['B2'].value, 'Meter Reading / C.u M / Payments per Month')
        self.assertEqual(sheet['B3'].value, 'Jan')
        self.assertEqual(sheet['M3'].value, 'Dec')
        self.assertEqual(sheet['N2'].value, 'Current Water Bill Balance')
        self.assertEqual(sheet['O2'].value, 'Installment Balance')
        self.assertEqual(sheet['P2'].value, 'Total Balance')

        self.assertEqual(sheet['A4'].value, 'ALPHA, ANA')
        self.assertEqual(sheet['B4'].value, 'Cu.M: 10\nPaid: 200.00')
        self.assertEqual(sheet['C4'].value, 'Cu.M: 3')
        self.assertEqual(sheet['N4'].value, 100)
        self.assertEqual(sheet['O4'].value, 300)
        self.assertEqual(sheet['P4'].value, 400)

        self.assertEqual(sheet['A5'].value, 'BRAVO, BEN')
        self.assertEqual(sheet['D5'].value, 'Paid: 150.00')
        self.assertEqual(sheet['N5'].value, 0)
        self.assertEqual(sheet['P5'].value, 0)

        self.assertEqual(sheet['A6'].value, 'TOTAL')
        self.assertEqual(sheet['N6'].value, 100)
        self.assertEqual(sheet['P6'].value, 400)

    def test_payments_are_attributed_to_the_billed_month(self):
        customer = WaterCustomer.objects.create(
            account_number='WA-2026-003',
            first_name='LOPE JR.',
            last_name='ABERGAS',
            meter_number='MTR-003',
        )
        bill_aug = WaterBill.objects.create(
            customer=customer,
            billing_period='2026-08',
            bill_date=date(2026, 8, 28),
            due_date=date(2026, 9, 15),
            consumption=63,
        )
        WaterBill.objects.create(
            customer=customer,
            billing_period='2026-09',
            bill_date=date(2026, 9, 28),
            due_date=date(2026, 10, 15),
            consumption=54,
        )
        bill_oct = WaterBill.objects.create(
            customer=customer,
            billing_period='2026-10',
            bill_date=date(2026, 10, 28),
            due_date=date(2026, 11, 15),
            consumption=48,
        )
        WaterPayment.objects.create(
            customer=customer,
            bill=bill_aug,
            purpose=WaterPayment.PURPOSE_BILL,
            payment_date=date(2026, 9, 8),
            amount=Decimal('1000.00'),
        )
        WaterPayment.objects.create(
            customer=customer,
            bill=bill_oct,
            purpose=WaterPayment.PURPOSE_BILL,
            payment_date=date(2026, 11, 16),
            amount=Decimal('1200.00'),
        )

        _, sheet = self._download(year=2026)
        row = self._row_for(sheet, 'ABERGAS, LOPE JR.')

        self.assertEqual(sheet.cell(row=row, column=9).value, 'Cu.M: 63\nPaid: 1,000.00')
        self.assertEqual(sheet.cell(row=row, column=10).value, 'Cu.M: 54')
        self.assertEqual(sheet.cell(row=row, column=11).value, 'Cu.M: 48\nPaid: 1,200.00')
        self.assertIsNone(sheet.cell(row=row, column=12).value)

    def test_payment_for_previous_year_bill_stays_in_billing_year(self):
        customer = WaterCustomer.objects.create(
            account_number='WA-2026-004',
            first_name='CROSS',
            last_name='YEAR',
            meter_number='MTR-004',
        )
        bill = WaterBill.objects.create(
            customer=customer,
            billing_period='2026-12',
            bill_date=date(2026, 12, 28),
            due_date=date(2027, 1, 15),
            consumption=5,
        )
        WaterPayment.objects.create(
            customer=customer,
            bill=bill,
            purpose=WaterPayment.PURPOSE_BILL,
            payment_date=date(2027, 1, 5),
            amount=Decimal('100.00'),
        )

        _, sheet = self._download(year=2026)
        row = self._row_for(sheet, 'YEAR, CROSS')
        self.assertEqual(sheet.cell(row=row, column=13).value, 'Cu.M: 5\nPaid: 100.00')

        _, sheet_next = self._download(year=2027)
        row_next = self._row_for(sheet_next, 'YEAR, CROSS')
        self.assertIsNone(sheet_next.cell(row=row_next, column=13).value)

    def test_installation_payments_are_excluded_from_month_cells(self):
        _, sheet = self._download(year=2026)
        self.assertEqual(sheet['B4'].value, 'Cu.M: 10\nPaid: 200.00')
        self.assertNotIn('500', sheet['B4'].value)

    def test_month_cell_includes_meter_reading_span(self):
        customer = WaterCustomer.objects.create(
            account_number='WA-2026-005',
            first_name='READ',
            last_name='METER',
            meter_number='MTR-005',
        )
        reading = WaterMeterReading.objects.create(
            customer=customer,
            billing_period='2026-04',
            reading_date=date(2026, 4, 5),
            previous_reading=350,
            current_reading=360,
        )
        bill = WaterBill.objects.create(
            customer=customer,
            meter_reading=reading,
            billing_period='2026-04',
            bill_date=date(2026, 4, 5),
            due_date=date(2026, 4, 20),
            consumption=10,
        )
        WaterPayment.objects.create(
            customer=customer,
            bill=bill,
            purpose=WaterPayment.PURPOSE_BILL,
            payment_date=date(2026, 4, 15),
            amount=Decimal('200.00'),
        )

        _, sheet = self._download(year=2026)
        row = self._row_for(sheet, 'METER, READ')
        self.assertEqual(
            sheet.cell(row=row, column=5).value,
            'Rdg: 350\u2192360\nCu.M: 10\nPaid: 200.00',
        )

    def test_year_defaults_to_current_year_when_missing_or_invalid(self):
        current_year = date.today().year

        response, _ = self._download()
        self.assertIn(f'water_customer_ledger_{current_year}.xlsx', response['Content-Disposition'])

        response, _ = self._download(year=1900)
        self.assertIn(f'water_customer_ledger_{current_year}.xlsx', response['Content-Disposition'])

    def test_reports_tab_renders_ledger_preview_and_export_link(self):
        response = self.client.get(
            reverse('water_billing_dashboard'),
            {'tab': 'reportsTab', 'report': 'customer_ledger', 'ledger_year': 2026},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Customer Monthly Ledger', content)
        self.assertIn('Export Excel', content)
        self.assertIn('ALPHA, ANA', content)
        self.assertIn('10 cu.m', content)
        self.assertIn('ledger-cum', content)
        self.assertIn('ledger-payment', content)

    def test_reports_tab_renders_zone_filter_options(self):
        response = self.client.get(
            reverse('water_billing_dashboard'),
            {'tab': 'reportsTab', 'report': 'customer_ledger', 'ledger_year': 2026},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('ledgerZone', content)
        self.assertIn('All zones', content)
        self.assertIn('ZONE NORTH', content)
        self.assertIn('ZONE SOUTH', content)

    def test_reports_tab_zone_filter_limits_ledger_rows(self):
        response = self.client.get(
            reverse('water_billing_dashboard'),
            {
                'tab': 'reportsTab',
                'report': 'customer_ledger',
                'ledger_year': 2026,
                'ledger_zone': self.zone_south.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('BRAVO, BEN', content)
        self.assertNotIn('ALPHA, ANA', content)

    def test_export_filters_by_zone_and_reflects_title(self):
        response, sheet = self._download(year=2026, zone=self.zone_north.id)

        self.assertIn(
            'water_customer_ledger_2026_zone_north.xlsx',
            response['Content-Disposition'],
        )
        self.assertEqual(sheet['A1'].value, 'CUSTOMER WATER LEDGER - 2026 - ZONE NORTH')
        names = [
            row[0].value
            for row in sheet.iter_rows(min_row=4, max_col=1)
            if row[0].value
        ]
        self.assertIn('ALPHA, ANA', names)
        self.assertNotIn('BRAVO, BEN', names)
        self.assertEqual(names[-1], 'TOTAL')

    def test_export_without_zone_keeps_default_title_and_filename(self):
        response, sheet = self._download(year=2026)
        self.assertIn('water_customer_ledger_2026.xlsx', response['Content-Disposition'])
        self.assertEqual(sheet['A1'].value, 'CUSTOMER WATER LEDGER - 2026')
