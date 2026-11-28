from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import WaterBill, WaterCustomer, WaterZone


class WaterBillingByZoneReportTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='water-zone-report-manager',
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
            zone=self.zone_north,
        )
        self.customer_b = WaterCustomer.objects.create(
            account_number='WA-2026-002',
            first_name='BEN',
            last_name='BRAVO',
            meter_number='MTR-002',
            zone=self.zone_south,
        )
        self.customer_c = WaterCustomer.objects.create(
            account_number='WA-2026-003',
            first_name='CAL',
            last_name='CHARLIE',
            meter_number='MTR-003',
        )

        self._make_bill(self.customer_a, '2026-01', date(2026, 1, 5), consumption=10)
        self._make_bill(self.customer_a, '2026-02', date(2026, 2, 5), consumption=6)
        self._make_bill(self.customer_b, '2026-01', date(2026, 1, 6), consumption=7)
        self._make_bill(self.customer_c, '2026-02', date(2026, 2, 6), consumption=2)
        self._make_bill(
            self.customer_a, '2026-01', date(2026, 1, 5), consumption=20, status='cancelled',
        )

    def _make_bill(self, customer, period, bill_date, consumption, status='unpaid'):
        return WaterBill.objects.create(
            customer=customer,
            billing_period=period,
            bill_date=bill_date,
            due_date=bill_date.replace(day=28),
            consumption=consumption,
            rate_per_cum=Decimal('20.00'),
            status=status,
        )

    def _get_report(self, year=2026):
        response = self.client.get(
            reverse('water_billing_dashboard'),
            {
                'tab': 'reportsTab',
                'report': 'billing_by_zone',
                'report_year': year,
                'fragment': '1',
            },
        )
        self.assertEqual(response.status_code, 200)
        return response, response.context['zone_report']

    def test_month_totals_per_zone(self):
        _, report = self._get_report()

        self.assertEqual(
            [month['period'] for month in report['months']],
            ['2026-01', '2026-02'],
        )
        zones = {row['zone_name']: row for row in report['zone_rows']}
        self.assertEqual(
            zones['ZONE NORTH']['month_totals'], [Decimal('200.00'), Decimal('120.00')]
        )
        self.assertEqual(zones['ZONE NORTH']['grand_total'], Decimal('320.00'))
        self.assertEqual(
            zones['ZONE SOUTH']['month_totals'], [Decimal('140.00'), Decimal('0.00')]
        )
        self.assertEqual(zones['UNASSIGNED']['month_totals'], [Decimal('0.00'), Decimal('100.00')])
        self.assertEqual(report['month_totals'], [Decimal('340.00'), Decimal('220.00')])
        self.assertEqual(report['grand_total'], Decimal('560.00'))

    def test_customers_listed_under_zone(self):
        _, report = self._get_report()
        zones = {row['zone_name']: row for row in report['zone_rows']}
        north = {c['account_number']: c for c in zones['ZONE NORTH']['customers']}
        self.assertEqual(north['WA-2026-001']['name'], 'ALPHA, ANA')
        self.assertEqual(north['WA-2026-001']['month_amounts'], [Decimal('200.00'), Decimal('120.00')])
        self.assertEqual(north['WA-2026-001']['total'], Decimal('320.00'))

    def test_cancelled_bills_are_excluded(self):
        _, report = self._get_report()
        zones = {row['zone_name']: row for row in report['zone_rows']}
        self.assertEqual(zones['ZONE NORTH']['grand_total'], Decimal('320.00'))

    def test_reports_tab_renders_matrix(self):
        response, _ = self._get_report()
        content = response.content.decode()
        self.assertIn('Billing by Zone (Monthly)', content)
        self.assertIn('ZONE NORTH', content)
        self.assertIn('ALPHA, ANA', content)
        self.assertIn('GRAND TOTAL', content)
        self.assertIn('reportYearFields', content)

    def test_csv_export_contains_zone_totals(self):
        response = self.client.get(
            reverse('water_billing_export_csv'),
            {'report': 'billing_by_zone', 'report_year': 2026},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('water_billing_by_zone_2026.csv', response['Content-Disposition'])
        content = response.content.decode()
        self.assertIn('Zone,Customer,Account,JAN,FEB,Grand Total', content)
        self.assertIn('ZONE NORTH,,,200.00,120.00,320.00', content)
        self.assertIn('GRAND TOTAL,,,340.00,220.00,560.00', content)
