from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/hr/', views.hr_dashboard, name='hr_dashboard'),
    path('dashboard/inventory/', views.inventory_dashboard, name='inventory_dashboard'),
    path('dashboard/sales/', views.sales_dashboard, name='sales_dashboard'),
    path('dashboard/sales/receipt/<int:order_id>/', views.sales_receipt, name='sales_receipt'),
    path('dashboard/payroll/', views.payroll_dashboard, name='payroll_dashboard'),
    path('logout/', views.logout_view, name='logout'),
]
