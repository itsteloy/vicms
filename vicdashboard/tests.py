from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import InventoryItem, SalesOrder


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
