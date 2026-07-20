from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/hr/', views.hr_dashboard, name='hr_dashboard'),
    path('dashboard/inventory/', views.inventory_dashboard, name='inventory_dashboard'),
    path('dashboard/inventory/purchase-order/pdf/', views.purchase_order_pdf, name='purchase_order_pdf'),
    path('dashboard/sales/', views.sales_dashboard, name='sales_dashboard'),
    path('dashboard/sales/quotation/save/', views.save_quotation, name='save_quotation'),
    path('dashboard/sales/quotation/<int:quotation_id>/download/', views.download_quotation_pdf, name='download_quotation_pdf'),
    path('dashboard/sales/receipt/<int:order_id>/', views.sales_receipt, name='sales_receipt'),
    path('dashboard/payroll/', views.payroll_dashboard, name='payroll_dashboard'),
    path('logout/', views.logout_view, name='logout'),
]
