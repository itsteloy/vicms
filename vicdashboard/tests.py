from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import views
from .models import (
    InventoryItem,
    SalesOrder,
    WaterCustomer,
    WaterOtherPayment,
    WaterPayment,
    WaterServiceContract,
)


class InventoryItemViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='manager',
            password='test-password-123',
        )
        self.client.force_login(self.user)

    def test_saving_item_via_post_persists_to_database(self):
        response = self.client.post(
            reverse('inventory_dashboard'),
            {
                'productCode': 'PRD-001',
                'itemName': 'Widget',
                'picture': '',
                'size': '10x10',
                'stockAvailable': '120',
                'pcsPerCtn': '25',
                'cartonSize': '1x1',
                'netWeight': '2.50',
                'grossWeight': '3.00',
                'price': '15.50',
                'description': 'Sample item',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(InventoryItem.objects.count(), 1)

        item = InventoryItem.objects.get()
        self.assertEqual(item.name, 'Widget')
        self.assertEqual(item.stock_available, 120)
        self.assertEqual(item.price, Decimal('15.50'))

    def test_recording_sale_reduces_inventory_stock(self):
        item = InventoryItem.objects.create(
            product_code='ELB-001',
            name='ELBOW',
            stock_available=10,
            price=Decimal('125.00'),
        )

        response = self.client.post(
            reverse('sales_dashboard'),
            {
                'customerName': 'ABC Construction',
                'inventoryItem': str(item.id),
                'quantity': '3',
                'notes': 'Invoice 1001',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(SalesOrder.objects.count(), 1)

        item.refresh_from_db()
        order = SalesOrder.objects.get()

        self.assertEqual(item.stock_available, 7)
        self.assertEqual(order.inventory_item, item)
        self.assertEqual(order.quantity, 3)
        self.assertEqual(order.unit_price, Decimal('125.00'))
        self.assertEqual(order.total_amount, Decimal('375.00'))

        receipt_response = self.client.get(reverse('sales_receipt', args=[order.id]))
        self.assertContains(receipt_response, 'VERSATEC Industrial Corporation')
        self.assertContains(receipt_response, 'Receipt #')

    def test_refunding_sale_restocks_inventory_and_updates_order(self):
        item = InventoryItem.objects.create(
            product_code='TEE-001',
            name='TEE',
            stock_available=10,
            price=Decimal('80.00'),
        )

        sale_response = self.client.post(
            reverse('sales_dashboard'),
            {
                'customerName': 'XYZ Builders',
                'inventoryItem': str(item.id),
                'quantity': '3',
                'notes': 'Invoice 2001',
            },
        )
        self.assertEqual(sale_response.status_code, 302)

        order = SalesOrder.objects.get()
        item.refresh_from_db()
        self.assertEqual(item.stock_available, 7)

        refund_response = self.client.post(
            reverse('sales_dashboard'),
            {
                'action': 'refund',
                'orderId': str(order.id),
                'refundQuantity': '2',
            },
            follow=True,
        )

        self.assertEqual(refund_response.status_code, 200)
        order.refresh_from_db()
        item.refresh_from_db()

        self.assertEqual(order.refund_quantity, 2)
        self.assertEqual(order.refund_status, 'partial')
        self.assertEqual(item.stock_available, 9)

    def test_dashboard_groups_item_names_and_tracks_per_product_code_metrics(self):
        item_one = InventoryItem.objects.create(
            product_code='TEE-001',
            name='TEE',
            stock_available=10,
            price=Decimal('15.00'),
        )
        item_two = InventoryItem.objects.create(
            product_code='TEE-002',
            name='TEE',
            stock_available=5,
            price=Decimal('20.00'),
        )
        SalesOrder.objects.create(
            customer_name='Alpha',
            inventory_item=item_one,
            quantity=2,
            unit_price=Decimal('15.00'),
            total_amount=Decimal('30.00'),
        )

        response = self.client.get(reverse('sales_dashboard'))

        self.assertEqual(response.status_code, 200)
        category_performance = response.context['page_obj'].object_list
        self.assertEqual(len(category_performance), 1)
        self.assertEqual(category_performance[0]['name'], 'TEE')

        variants = category_performance[0]['variants']
        self.assertEqual(sorted(variant['code'] for variant in variants), ['TEE-001', 'TEE-002'])

        selected_variant = next(variant for variant in variants if variant['code'] == 'TEE-001')
        self.assertEqual(selected_variant['quantity'], 2)
        self.assertEqual(selected_variant['revenue'], 30.0)
        self.assertEqual(selected_variant['orders'], 1)
        self.assertEqual(selected_variant['stock'], 10)

    def test_dashboard_paginates_category_cards_after_two_rows(self):
        for index in range(7):
            InventoryItem.objects.create(
                product_code=f'CAT-{index:02d}',
                name=f'Category {index}',
                stock_available=3,
                price=Decimal('10.00'),
            )

        response = self.client.get(reverse('sales_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 1)
        self.assertEqual(len(response.context['page_obj'].object_list), 6)
        self.assertTrue(response.context['page_obj'].has_next())
        self.assertEqual(response.context['page_obj'].paginator.num_pages, 2)


class WaterServiceContractCustomerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='water-manager',
            password='test-password-123',
        )
        self.client.force_login(self.user)

    def _post_application(self, **overrides):
        payload = {
            'action': 'create_service_contract',
            'application_status': 'new',
            'last_name': 'Dela Cruz',
            'first_name': 'Juan',
            'zone_purok': 'Zone 1',
            'barangay': 'Poblacion',
            'municipality_city': 'Davao',
            'contact_number': '09171234567',
            'customer_classification': 'residential',
            'meter_number': 'MTR-001',
            'connection_location': '123 Main St',
            'ack_ar_number': 'AR-001',
            'ack_amount': '3000.00',
            'ack_date': '2026-10-20',
        }
        payload.update(overrides)
        return self.client.post(reverse('water_billing_dashboard'), payload)

    def test_new_application_creates_and_links_customer(self):
        response = self._post_application()

        self.assertEqual(response.status_code, 302)
        contract = WaterServiceContract.objects.get()
        customer = WaterCustomer.objects.get()

        self.assertEqual(contract.customer_id, customer.id)
        self.assertEqual(customer.display_name, 'DELA CRUZ, JUAN')
        self.assertEqual(customer.service_address, '123 MAIN ST')
        self.assertEqual(customer.contact_number, '09171234567')
        self.assertEqual(customer.meter_number, 'MTR-001')
        self.assertEqual(customer.zone.name, 'ZONE 1')
        self.assertEqual(customer.customer_type, 'residential')
        self.assertEqual(customer.connection_status, 'active')
        self.assertEqual(customer.installment_balance, Decimal('2900.00'))
        self.assertTrue(
            WaterPayment.objects.filter(
                customer=customer,
                purpose=WaterPayment.PURPOSE_INSTALLATION,
                amount=Decimal('3000.00'),
                ar_number='AR-001',
            ).exists()
        )
        weekly_rows, weekly_totals, _ = views._water_weekly_collection_rows(
            date(2026, 10, 19),
            date(2026, 10, 25),
        )
        self.assertTrue(
            any(
                row['ar_number'] == 'AR-001'
                and row['installation_fee'] == Decimal('3000.00')
                for row in weekly_rows
            )
        )
        self.assertEqual(weekly_totals['installation_fee'], Decimal('3000.00'))

    def test_new_application_payment_requires_an_ar_number(self):
        response = self._post_application(ack_ar_number='')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(WaterCustomer.objects.count(), 0)
        self.assertEqual(WaterServiceContract.objects.count(), 0)
        self.assertEqual(WaterPayment.objects.count(), 0)

    def test_new_application_links_existing_customer_instead_of_duplicating(self):
        existing = WaterCustomer.objects.create(
            first_name='Juan',
            last_name='Dela Cruz',
            service_address='123 MAIN ST',
            contact_number='09171234567',
            meter_number='MTR-001',
            installment_balance=Decimal('500.00'),
        )

        self._post_application()

        self.assertEqual(WaterCustomer.objects.count(), 1)
        contract = WaterServiceContract.objects.get()
        existing.refresh_from_db()
        self.assertEqual(contract.customer_id, existing.id)
        self.assertEqual(existing.installment_balance, Decimal('500.00'))

    def test_reconnection_does_not_create_a_new_customer(self):
        existing = WaterCustomer.objects.create(
            first_name='Juan',
            last_name='Dela Cruz',
            meter_number='MTR-001',
        )

        response = self._post_application(
            application_status='reconnection',
            contract_customer_id=str(existing.id),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(WaterCustomer.objects.count(), 1)
        contract = WaterServiceContract.objects.get()
        self.assertEqual(contract.customer_id, existing.id)

class SalesSummaryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='sales-summary-user',
            password='test-password-123',
        )
        self.client.force_login(self.user)
        self.customer = WaterCustomer.objects.create(
            first_name='Maria',
            last_name='Santos',
            meter_number='MTR-SS-1',
        )
        WaterPayment.objects.create(
            customer=self.customer,
            payment_date=date(2026, 9, 15),
            amount=Decimal('500.00'),
            payment_method='cash',
            ar_number='2801',
        )
        WaterPayment.objects.create(
            customer=self.customer,
            payment_date=date(2026, 10, 2),
            amount=Decimal('300.00'),
            payment_method='gcash',
            ar_number='2802',
        )

    def test_sales_summary_groups_by_month_and_extracts_vat(self):
        response = self.client.get(reverse('sales_dashboard'), {'tab': 'sales-tab'})

        self.assertEqual(response.status_code, 200)
        months = response.context['sales_summary_months']
        self.assertEqual([month['key'] for month in months], ['2026-09', '2026-10'])

        selected = response.context['sales_summary']
        self.assertEqual(selected['key'], '2026-10')
        self.assertEqual(selected['totals']['gross'], Decimal('300.00'))
        self.assertEqual(selected['totals']['output_vat'], Decimal('32.14'))
        self.assertEqual(selected['totals']['net'], Decimal('267.86'))
        self.assertContains(response, 'SALES SUMMARY')
        self.assertContains(response, 'OCTOBER, 2026')

    def test_sales_summary_month_filter_and_date_order(self):
        WaterPayment.objects.create(
            customer=self.customer,
            payment_date=date(2026, 9, 14),
            amount=Decimal('100.00'),
            payment_method='cash',
            ar_number='2799',
        )

        response = self.client.get(
            reverse('sales_dashboard'),
            {'tab': 'sales-tab', 'sales_month': '2026-09'},
        )

        selected = response.context['sales_summary']
        self.assertEqual(selected['key'], '2026-09')
        self.assertEqual(
            [row['ar_number'] for row in selected['rows']],
            ['2799', '2801'],
        )
        self.assertEqual(selected['totals']['gross'], Decimal('600.00'))

    def test_sales_summary_orders_by_date_then_displayed_number(self):
        WaterPayment.objects.create(
            customer=self.customer,
            payment_date=date(2026, 9, 10),
            amount=Decimal('200.00'),
            payment_method='cash',
            ar_number='2900',
        )
        WaterPayment.objects.create(
            customer=self.customer,
            payment_date=date(2026, 9, 10),
            amount=Decimal('150.00'),
            payment_method='cash',
            ar_number='2850',
        )
        WaterPayment.objects.create(
            customer=self.customer,
            payment_date=date(2026, 9, 12),
            amount=Decimal('125.00'),
            payment_method='cash',
            ar_number='2799',
        )
        WaterOtherPayment.objects.create(
            payment_date=date(2026, 9, 10),
            ar_number='SI0245',
            received_from='MARIPHIL',
            amount=Decimal('100.00'),
            payment_of='Water Bill',
        )

        response = self.client.get(
            reverse('sales_dashboard'),
            {'tab': 'sales-tab', 'sales_month': '2026-09'},
        )

        rows = response.context['sales_summary']['rows']
        self.assertEqual(
            [row['date'] for row in rows],
            [
                date(2026, 9, 10),
                date(2026, 9, 10),
                date(2026, 9, 10),
                date(2026, 9, 12),
                date(2026, 9, 15),
            ],
        )
        self.assertEqual(
            [row['display_ar_number'] for row in rows],
            ['245', '2850', '2900', '2799', '2801'],
        )

    def test_sales_summary_si_type_and_mindanao_display_numbers(self):
        WaterOtherPayment.objects.create(
            payment_date=date(2026, 9, 11),
            ar_number='SI0235',
            received_from='MINDANAO INTEGRATED LOGISTICS SERVICES',
            amount=Decimal('2400.00'),
            payment_of='Water Bill',
        )
        WaterOtherPayment.objects.create(
            payment_date=date(2026, 9, 12),
            ar_number='0236',
            received_from='MINDANAO INTEGRATED LOGISTICS SERVICES',
            amount=Decimal('2400.00'),
            payment_of='Water Bill',
        )
        WaterOtherPayment.objects.create(
            payment_date=date(2026, 9, 13),
            ar_number='SI0245',
            received_from='MARIPHIL',
            amount=Decimal('100.00'),
            payment_of='Water Bill',
        )

        response = self.client.get(
            reverse('sales_dashboard'),
            {'tab': 'sales-tab', 'sales_month': '2026-09'},
        )

        rows = {
            row['ar_number']: row
            for row in response.context['sales_summary']['rows']
        }
        self.assertEqual(rows['SI0235']['or_type'], 'SI')
        self.assertEqual(rows['SI0235']['display_ar_number'], '235')
        self.assertEqual(rows['0236']['or_type'], 'SI')
        self.assertEqual(rows['0236']['display_ar_number'], '236')
        self.assertEqual(rows['SI0245']['or_type'], 'SI')
        self.assertEqual(rows['SI0245']['display_ar_number'], '245')
        self.assertEqual(rows['2801']['or_type'], 'AR')
        self.assertEqual(rows['2801']['display_ar_number'], '2801')
        self.assertContains(response, '<td class="col-no">235</td>', html=True)
        self.assertContains(response, '<td class="col-no">245</td>', html=True)
        self.assertNotContains(response, '<td class="col-no">SI0245</td>', html=True)

    def test_sales_summary_shortens_long_ar_numbers(self):
        cases = [
            ('003048', 'DONAYRE, ARSENIO', '3048'),
            ('03047', 'ELMAR MERINGUEZ', '3047'),
            ('03310', 'JING JING BERNADAS', '3310'),
            ('0386', 'NILO CASTRO', '0386'),
            ('2845 & 2847', 'SULTAN, NORAINA', '2847'),
        ]
        for ar_number, received_from, _display in cases:
            WaterOtherPayment.objects.create(
                payment_date=date(2026, 9, 24),
                ar_number=ar_number,
                received_from=received_from,
                amount=Decimal('100.00'),
                payment_of='Water Bill',
            )

        response = self.client.get(
            reverse('sales_dashboard'),
            {'tab': 'sales-tab', 'sales_month': '2026-09'},
        )

        rows = {
            row['ar_number']: row
            for row in response.context['sales_summary']['rows']
        }
        for ar_number, _received_from, expected_display in cases:
            self.assertEqual(rows[ar_number]['or_type'], 'AR')
            self.assertEqual(rows[ar_number]['display_ar_number'], expected_display)
        self.assertContains(response, '<td class="col-no">3048</td>', html=True)
        self.assertContains(response, '<td class="col-no">3047</td>', html=True)


class WaterReconnectionPaymentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='water-payments',
            password='test-password-123',
        )
        self.client.force_login(self.user)

    def _post_payment(self, **overrides):
        payload = {
            'action': 'create_payment',
            'payment_purpose': 'reconnection',
            'ar_number': 'RC-001',
            'payment_date': '2026-10-21',
            'received_from': 'JUAN DELA CRUZ',
            'address': 'PUROK 1',
            'payment_of': 'Reconnection fee',
            'amount': '500.00',
            'amount_received_status': 'not_received',
            'remarks': 'Reconnection',
        }
        payload.update(overrides)
        return self.client.post(reverse('water_billing_dashboard'), payload)

    def test_reconnection_payment_creates_reconnection_ledger_entry(self):
        response = self._post_payment()

        self.assertEqual(response.status_code, 302)
        payment = WaterOtherPayment.objects.get()
        self.assertEqual(
            payment.payment_type,
            WaterOtherPayment.PAYMENT_TYPE_RECONNECTION,
        )
        self.assertEqual(payment.amount, Decimal('500.00'))

        rows, totals, _ = views._water_weekly_collection_rows(
            date(2026, 10, 19),
            date(2026, 10, 25),
        )
        self.assertEqual(totals['reconnection_fee'], Decimal('500.00'))
        self.assertTrue(
            any(
                row['ar_number'] == 'RC-001'
                and row['reconnection_fee'] == Decimal('500.00')
                for row in rows
            )
        )

    def test_other_payment_stays_in_other_category(self):
        response = self._post_payment(
            payment_purpose='other',
            ar_number='OR-001',
            payment_of='Parcel',
        )

        self.assertEqual(response.status_code, 302)
        payment = WaterOtherPayment.objects.get()
        self.assertEqual(
            payment.payment_type,
            WaterOtherPayment.PAYMENT_TYPE_OTHER,
        )
        _rows, totals, _ = views._water_weekly_collection_rows(
            date(2026, 10, 19),
            date(2026, 10, 25),
        )
        self.assertEqual(totals['reconnection_fee'], Decimal('0.00'))
