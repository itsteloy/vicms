from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('workspace/login/', views.workspace_login, name='workspace_login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/hr/', views.hr_dashboard, name='hr_dashboard'),
    path('dashboard/inventory/', views.inventory_dashboard, name='inventory_dashboard'),
    path('dashboard/inventory/purchase-order/pdf/', views.purchase_order_pdf, name='purchase_order_pdf'),
    path('dashboard/sales/', views.sales_dashboard, name='sales_dashboard'),
    path('dashboard/sales/quotation/save/', views.save_quotation, name='save_quotation'),
    path('dashboard/sales/quotation/<int:quotation_id>/download/', views.download_quotation_pdf, name='download_quotation_pdf'),
    path('dashboard/sales/receipt/<int:order_id>/', views.sales_receipt, name='sales_receipt'),
    path('dashboard/payroll/', views.payroll_dashboard, name='payroll_dashboard'),
    path('dashboard/accounting_dashboard/', views.accounting_dashboard, name='accounting_dashboard'),
    path('dashboard/services_dashboard/', views.services_dashboard, name='services_dashboard'),
    path('dashboard/services/repair-reports/create/', views.create_service_repair_report, name='create_service_repair_report'),
    path('dashboard/services/job-orders/create/', views.create_job_order, name='create_job_order'),
    path('dashboard/services/repair-reports/<int:report_id>/', views.view_service_repair_report, name='view_service_repair_report'),
    path('dashboard/services/repair-reports/<int:report_id>/edit/', views.edit_service_repair_report, name='edit_service_repair_report'),
    path('dashboard/services/repair-reports/<int:report_id>/delete/', views.delete_service_repair_report, name='delete_service_repair_report'),
    path('dashboard/services/job-orders/<int:order_id>/', views.view_job_order, name='view_job_order'),
    path('dashboard/services/job-orders/<int:order_id>/edit/', views.edit_job_order, name='edit_job_order'),
    path('dashboard/services/job-orders/<int:order_id>/delete/', views.delete_job_order, name='delete_job_order'),
    path('logout/', views.logout_view, name='logout'),
]
