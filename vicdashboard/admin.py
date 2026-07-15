from django.contrib import admin
from .models import InventoryItem, SalesOrder


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'product_code', 'stock_available', 'pcs_per_ctn', 'price', 'created_at')
    search_fields = ('name', 'product_code', 'description')


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'inventory_item', 'quantity', 'unit_price', 'total_amount', 'created_at')
    search_fields = ('customer_name', 'inventory_item__name', 'inventory_item__product_code')
