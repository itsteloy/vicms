from datetime import datetime
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from .models import AgeingOfAccountsReport


class AgeingAccountsImportTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='ageing-manager',
            password='test-password-123',
        )
        self.client.force_login(user)

    def _workbook_file(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet['A1'] = 'METRO DAVAO SUPREME PUMPS INDUSTRIES, INC.'
        sheet['A4'] = 'AGEING OF ACCOUNTS AS OCTOBER 30 , 2026'
        sheet.append([])
        sheet.append([
            'DATE', 'CUSTOMERS NAME', 'PO NO.', 'AGENT', 'BI#', 'SI#',
            'CR#', 'CI#', 'AR#', 'DR NO.', 'AMOUNT', 'AMOUNT PAID',
            'PAID ITEMS',
        ])
        sheet.append([
            datetime(2026, 10, 12), 'Sample Customer', 'PO-10', 'JAA',
            None, 'SI-10', None, None, None, 'DR-10', 30466428.26, 25127417.02,
            'Paid part',
        ])
        sheet.append([
            datetime(2026, 10, 15), 'Unpriced Customer', None, 'AID',
            None, None, None, None, None, 'DR-11', 'NO PRICE', None, None,
        ])
        sheet.append([
            None, 'GRAND TOTAL', None, None, None, None, None, None, None,
            None, 30466428.26, 25127417.02, None,
        ])
        file_data = BytesIO()
        workbook.save(file_data)
        return file_data.getvalue()

    def test_import_reads_excel_header_and_date_and_calculates_balance(self):
        upload = SimpleUploadedFile(
            'ageing.xlsx',
            self._workbook_file(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response = self.client.post(
            reverse('import_ageing_accounts_upload'),
            {'xlsx': upload},
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload['as_of_date'], '2026-10-30')
        self.assertEqual(payload['total_amount'], '30466428.26')
        self.assertEqual(payload['total_amount_paid'], '25127417.02')
        self.assertEqual(payload['total_balance_due'], '5339011.24')
        self.assertEqual(len(payload['lines']), 2)
        self.assertEqual(payload['lines'][0]['balance_due'], '5339011.24')
        self.assertEqual(payload['lines'][1]['balance_due'], '')

        report = AgeingOfAccountsReport.objects.get(pk=payload['id'])
        self.assertEqual(report.as_of_date.isoformat(), '2026-10-30')
        self.assertEqual(report.total_balance_due, Decimal('5339011.24'))

    def test_import_rejects_an_invalid_xlsx_file(self):
        upload = SimpleUploadedFile('broken.xlsx', b'not an Excel workbook')
        response = self.client.post(
            reverse('import_ageing_accounts_upload'),
            {'xlsx': upload},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('valid .xlsx', response.json()['error'])
