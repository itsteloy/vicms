from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps
from .models import InventoryItem, SalesOrder, HRDocument, Employee, PayPeriod, PayrollRun, PayrollLine, DeductionConfig, EmployeeDeduction,TaxBracket, AttendanceLog, ShiftSchedule, LeaveBalance, LeaveRequest, Holiday, RefundRecord, Delivery, DeliveryLine, Quotation, QuotationLine, ServiceRepairReport, JobOrder, WorkspaceAccount
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.template.loader import render_to_string
from django.conf import settings
from django.templatetags.static import static
from django.utils import timezone
from .po_pdf import build_purchase_order_pdf
from .forms import JobOrderForm, ServiceRepairReportForm
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Sum, Count, Q
import traceback
import json

MANAGEMENT_MODULES = [
    {
        'name': 'HR',
        'summary': 'Employee records, attendance, onboarding, and staff requests.',
        'status': 'Active',
        'url_name': 'hr_dashboard',
        'workspace_key': 'hr',
    },
    {
        'name': 'Inventory',
        'summary': 'Product catalog, images, carton details, weights, and pricing.',
        'status': 'Active',
        'url_name': 'inventory_dashboard',
        'workspace_key': 'inventory',
    },
    {
        'name': 'Sales',
        'summary': 'Customer orders, quotations, invoices, and sales pipeline.',
        'status': 'Active',
        'url_name': 'sales_dashboard',
        'workspace_key': 'sales',
    },
    {
        'name': 'Payroll',
        'summary': 'Salary records, deductions, approvals, and pay schedules.',
        'status': 'Active',
        'url_name': 'payroll_dashboard',
        'workspace_key': 'payroll',
    },
    {
        'name': 'Accounting',
        'summary': 'Salary records, deductions, approvals, and pay schedules.',
        'status': 'Active',
        'url_name': 'accounting_dashboard',
        'workspace_key': 'accounting',
    },
    {
        'name': 'Services',
        'summary': 'Service Repair Reports and Job Orders',
        'status': 'Active',
        'url_name': 'services_dashboard',
        'workspace_key': 'services',
    }
]

INVENTORY_ITEM_OPTIONS = [
    'COUPLING',
    'ELBOW',
    'TEE',
    'REDUCING COUPLING',
    'REDUCING TEE',
    'PLUG',
    'MALE ADAPTOR',
    'FEMALE ADAPTOR',
    'MALE ELBOW',
    'FEMALE ELBOW',
    'MALE TEE',
    'FEMALE TEE',
    'RESTRAINT FLANGE ADAPTOR',
    'RESTRAINT COUPLING',
    'SLEEVE TYPE COUPLING',
    'REPAIR CLAMP',
    'WATER PIPES',
    'PE-TECH',
    
]


def get_user_workspace(user):
    if not user.is_authenticated:
        return None
    return WorkspaceAccount.objects.filter(user=user, is_active=True).select_related('user').first()


def user_has_dashboard_access(user, url_name):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    workspace = get_user_workspace(user)
    if workspace is None:
        return True
    return workspace.dashboard_url_name == url_name


def require_dashboard(url_name):
    def decorator(view_func):
        @wraps(view_func)
        @never_cache
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                module = _module_by_url_name(url_name)
                workspace_key = module['workspace_key'] if module else ''
                dashboard_url = reverse('dashboard')
                if workspace_key:
                    return redirect(f'{dashboard_url}?workspace={workspace_key}')
                return redirect('dashboard')
            if not user_has_dashboard_access(request.user, url_name):
                messages.error(request, 'You do not have access to this workspace.')
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def _module_by_workspace_key(workspace_key):
    for module in MANAGEMENT_MODULES:
        if module['workspace_key'] == workspace_key:
            return module
    return None


def _module_by_url_name(url_name):
    for module in MANAGEMENT_MODULES:
        if module['url_name'] == url_name:
            return module
    return None


def landing(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    return render(
        request,
        'landing.html',
        {
            'modules': MANAGEMENT_MODULES,
        },
    )


def workspace_login(request):
    if request.method != 'POST':
        workspace_key = request.GET.get('workspace', '').strip()
        if workspace_key:
            return redirect(f"{reverse('dashboard')}?workspace={workspace_key}")
        return redirect('dashboard')

    workspace_key = request.POST.get('workspace_key', '').strip()
    module = _module_by_workspace_key(workspace_key)
    form = AuthenticationForm(request, data=request.POST)

    if not module:
        messages.error(request, 'Invalid workspace selected.')
        return redirect('dashboard')

    if form.is_valid():
        user = form.get_user()
        workspace = WorkspaceAccount.objects.filter(
            workspace_key=workspace_key,
            is_active=True,
        ).select_related('user').first()

        if not workspace:
            messages.error(request, 'This workspace is not available.')
        elif not (user.is_staff or user.is_superuser) and workspace.user_id != user.id:
            messages.error(request, f'Invalid credentials for the {module["name"]} workspace.')
        else:
            login(request, user)
            messages.success(request, f'Welcome to the {module["name"]} workspace.')
            return redirect(module['url_name'])

    messages.error(request, 'Invalid username or password.')
    return redirect(f"{reverse('dashboard')}?workspace={workspace_key}&login_error=1")


@never_cache
def logout_view(request):
    logout(request)
    list(messages.get_messages(request))
    messages.success(request, 'You have been signed out.')
    return redirect('dashboard')


@never_cache
def dashboard(request):
    is_authenticated = request.user.is_authenticated
    workspace_accounts = {
        account.workspace_key: account
        for account in WorkspaceAccount.objects.filter(is_active=True).select_related('user')
    }
    modules = []
    for module in MANAGEMENT_MODULES:
        item = dict(module)
        item['workspace_account'] = workspace_accounts.get(module['workspace_key'])
        item['can_access'] = (
            is_authenticated
            and user_has_dashboard_access(request.user, module['url_name'])
        )
        modules.append(item)

    selected_workspace = request.GET.get('workspace', '').strip()
    selected_module = _module_by_workspace_key(selected_workspace)
    login_error = request.GET.get('login_error') == '1'

    return render(
        request,
        'dashboard_select.html',
        {
            'modules': modules,
            'workspace_account': get_user_workspace(request.user) if is_authenticated else None,
            'selected_workspace': selected_workspace if selected_module else '',
            'selected_module': selected_module,
            'login_error': login_error,
            'is_authenticated': is_authenticated,
        },
    )


@require_dashboard('hr_dashboard')
def hr_dashboard(request):
    if request.method == 'POST':
        action = request.POST.get('action', '').strip()

        # Upload new document
        if action == 'upload':
            title = request.POST.get('title', '').strip()
            doc_type = request.POST.get('document_type', 'other')
            status = request.POST.get('status', 'pending')
            file = request.FILES.get('file')

            if not title or not file:
                messages.error(request, 'Title and file are required.')
            else:
                HRDocument.objects.create(
                    title=title,
                    file=file,
                    document_type=doc_type,
                    status=status,
                )
                messages.success(request, 'Document uploaded successfully.')
            return redirect('hr_dashboard')

        # Delete a document
        if action == 'delete':
            doc_id = request.POST.get('doc_id', '').strip()
            if doc_id:
                try:
                    doc = HRDocument.objects.get(pk=doc_id)
                    doc.delete()
                    messages.success(request, 'Document deleted.')
                except HRDocument.DoesNotExist:
                    messages.error(request, 'Document not found.')
            return redirect('hr_dashboard')

        # Update document status (e.g., approve/reject)
        if action == 'update_status':
            doc_id = request.POST.get('doc_id', '').strip()
            new_status = request.POST.get('status', '').strip()
            if doc_id and new_status in dict(HRDocument.STATUS_CHOICES):
                try:
                    doc = HRDocument.objects.get(pk=doc_id)
                    doc.status = new_status
                    doc.save()
                    messages.success(request, f'Document status updated to {new_status}.')
                except HRDocument.DoesNotExist:
                    messages.error(request, 'Document not found.')
            return redirect('hr_dashboard')

    # Fetch all documents for display
    documents = HRDocument.objects.all()
    return render(
        request,
        'hr_dashboard.html',
        {
            'modules': MANAGEMENT_MODULES,
            'documents': documents,
            'document_types': HRDocument.DOCUMENT_TYPES,
            'status_choices': HRDocument.STATUS_CHOICES,
        },
    )


@require_dashboard('sales_dashboard')
def sales_dashboard(request):
    if request.method == 'POST':
        action = request.POST.get('action', '').strip()

        if action == 'refund':
            order_id = request.POST.get('orderId', '').strip()
            try:
                refund_quantity = int(request.POST.get('refundQuantity', 0) or 0)
            except ValueError:
                refund_quantity = 0

            if not order_id or refund_quantity <= 0:
                messages.error(request, 'Select a sale and enter a valid refund quantity.')
                return redirect('sales_dashboard')

            try:
                with transaction.atomic():
                    order = SalesOrder.objects.select_for_update().get(pk=order_id)
                    if order.refund_quantity + refund_quantity > order.quantity:
                        messages.error(request, 'Refund quantity cannot exceed the remaining sold quantity.')
                        return redirect('sales_dashboard')

                    if order.refund_quantity >= order.quantity:
                        messages.error(request, 'This sale has already been fully refunded.')
                        return redirect('sales_dashboard')

                    item = InventoryItem.objects.select_for_update().get(pk=order.inventory_item_id)
                    order.refund_quantity += refund_quantity
                    order.refund_amount += order.unit_price * refund_quantity
                    order.refund_status = 'full' if order.refund_quantity >= order.quantity else 'partial'
                    order.save(update_fields=['refund_quantity', 'refund_amount', 'refund_status'])
                    item.stock_available += refund_quantity
                    item.save(update_fields=['stock_available', 'updated_at'])


                    RefundRecord.objects.create(
                        sales_order=order,
                        refund_quantity=refund_quantity,
                        refund_amount=order.unit_price * refund_quantity,
                        reason=request.POST.get('reason', ''),
                        processed_by=request.user,
                    )
                    messages.success(request, 'Refund recorded and inventory stock restored.')
                    return redirect('sales_dashboard')
            except SalesOrder.DoesNotExist:
                messages.error(request, 'Selected sale does not exist.')
            except InventoryItem.DoesNotExist:
                messages.error(request, 'The linked inventory item could not be found.')

            return redirect('sales_dashboard')

        customer_name = request.POST.get('customerName', '').strip()
        item_id = request.POST.get('inventoryItem', '').strip()
        notes = request.POST.get('notes', '').strip()
        try:
            quantity = int(request.POST.get('quantity', 0) or 0)
        except ValueError:
            quantity = 0

        if not customer_name or not item_id or quantity <= 0:
            messages.error(request, 'Complete the customer, item, and quantity before recording a sale.')
            return redirect('sales_dashboard')

        try:
            with transaction.atomic():
                item = InventoryItem.objects.select_for_update().get(pk=item_id)
                if quantity > item.stock_available:
                    messages.error(request, f'Only {item.stock_available} stock available for {item.name}.')
                    return redirect('sales_dashboard')

                unit_price = item.price
                order = SalesOrder.objects.create(
                    customer_name=customer_name,
                    inventory_item=item,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_amount=unit_price * quantity,
                    notes=notes,
                    customer_contact=request.POST.get('customerContact', '').strip(),
                    payment_method=request.POST.get('paymentMethod', 'cash'),
                )
                item.stock_available -= quantity
                item.save(update_fields=['stock_available', 'updated_at'])
                messages.success(request, 'Sale recorded and inventory stock updated.')
                return redirect('sales_receipt', order_id=order.id)
        except InventoryItem.DoesNotExist:
            messages.error(request, 'Selected inventory item does not exist.')

        return redirect('sales_dashboard')

    inventory_items = InventoryItem.objects.all().order_by('name', 'product_code')
    sales_orders = SalesOrder.objects.select_related('inventory_item').all()[:5]
    total_sales = sum(order.total_amount for order in sales_orders)
    total_quantity_sold = sum(order.quantity for order in sales_orders)

    sales_for_analytics = SalesOrder.objects.select_related('inventory_item').all()
    total_revenue = sum(order.total_amount for order in sales_for_analytics)
    total_profit = sum((order.total_amount - (order.unit_price * order.refund_quantity)) for order in sales_for_analytics)

    today = datetime.now().date()
    daily_sales = sales_for_analytics.filter(created_at__date=today)
    weekly_sales = sales_for_analytics.filter(created_at__date__gte=today - timedelta(days=7))
    monthly_sales = sales_for_analytics.filter(created_at__date__gte=today - timedelta(days=30))

    def build_period_summary(queryset, group_by):
        grouped = defaultdict(Decimal)
        for order in queryset:
            if group_by == 'day':
                key = order.created_at.strftime('%Y-%m-%d')
            elif group_by == 'week':
                key = f"W{order.created_at.isocalendar().week:02d}".format(k=order.created_at.isocalendar().week)
            else:
                key = order.created_at.strftime('%Y-%m')
            grouped[key] += order.total_amount

        summary = []
        for key in sorted(grouped):
            summary.append({
                'label': key,
                'amount': float(grouped[key]),
            })
        return summary

    daily_summary = build_period_summary(daily_sales, 'day')
    weekly_summary = build_period_summary(weekly_sales, 'week')
    monthly_summary = build_period_summary(monthly_sales, 'month')

    category_performance = []
    sales_by_category = defaultdict(lambda: {
        'name': '',
        'variants': [],
        'stock': 0,
    })

    for item in inventory_items:
        key = item.name.strip().lower()
        entry = sales_by_category[key]
        entry['name'] = item.name
        entry['variants'].append({
            'code': item.product_code or 'No code',
            'quantity': 0,
            'revenue': 0.0,
            'orders': 0,
            'stock': item.stock_available,
        })
        entry['stock'] = max(entry['stock'], item.stock_available)

    for order in sales_for_analytics:
        key = order.inventory_item.name.strip().lower()
        entry = sales_by_category[key]
        entry['name'] = order.inventory_item.name
        match = next((variant for variant in entry['variants'] if variant['code'] == (order.inventory_item.product_code or 'No code')), None)
        if match is None:
            entry['variants'].append({
                'code': order.inventory_item.product_code or 'No code',
                'quantity': 0,
                'revenue': 0.0,
                'orders': 0,
                'stock': order.inventory_item.stock_available,
            })
            match = entry['variants'][-1]
        match['quantity'] += order.quantity
        match['revenue'] += float(order.total_amount)
        match['orders'] += 1
        match['stock'] = order.inventory_item.stock_available
        entry['stock'] = max(entry['stock'], order.inventory_item.stock_available)

    for entry in sales_by_category.values():
        entry['variants'].sort(key=lambda variant: variant['code'])
        category_performance.append({
            'name': entry['name'],
            'variants': entry['variants'],
            'stock': entry['stock'],
        })

    category_performance.sort(key=lambda item: max(variant['revenue'] for variant in item['variants']), reverse=True)

    page_size = 8
    paginator = Paginator(category_performance, page_size)
    page_number = request.GET.get('page', 1)

    category_chart_data = []
    for cat in category_performance:
        total_rev = sum(v['revenue'] for v in cat['variants'])
        total_qty = sum(v['quantity'] for v in cat['variants'])
        category_chart_data.append({
            'name': cat['name'],
            'revenue': total_rev,
            'quantity': total_qty,
        })
    category_chart_data.sort(key=lambda x: x['revenue'], reverse=True)
    category_chart_data = category_chart_data[:10]

    max_revenue = max((c['revenue'] for c in category_chart_data), default=1)
    max_quantity = max((c['quantity'] for c in category_chart_data), default=1)

    for cat in category_chart_data:
        cat['revenue_percent'] = (cat['revenue'] / max_revenue * 100) if max_revenue else 0
        cat['quantity_percent'] = (cat['quantity'] / max_quantity * 100) if max_quantity else 0

    if len(category_performance) <= page_size:
        page_obj = paginator.get_page(1)
        show_pagination = False
    else:
        page_obj = paginator.get_page(page_number)
        show_pagination = page_obj.has_other_pages()

    hourly_groups = defaultdict(int)
    for order in sales_for_analytics:
        hourly_groups[order.created_at.strftime('%H:00')] += int(order.total_amount)

    peak_hour = max(hourly_groups.items(), key=lambda pair: pair[1], default=(None, 0))[0]
    refund_history = RefundRecord.objects.select_related('sales_order', 'processed_by').order_by('-refund_date')[:10]
    sales_history_qs = SalesOrder.objects.select_related('inventory_item').all()

    # Apply filters from GET parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    customer = request.GET.get('customer')
    item_name = request.GET.get('item')
    refund_status = request.GET.get('refund_status')

    if start_date and end_date:
        sales_history_qs = sales_history_qs.filter(created_at__date__range=[start_date, end_date])
    if customer:
        sales_history_qs = sales_history_qs.filter(customer_name__icontains=customer)
    if item_name:
        sales_history_qs = sales_history_qs.filter(inventory_item__name__icontains=item_name)
    if refund_status and refund_status != 'all':
        if refund_status == 'none':
            sales_history_qs = sales_history_qs.filter(refund_status='none')
        elif refund_status == 'partial':
            sales_history_qs = sales_history_qs.filter(refund_status='partial')
        elif refund_status == 'full':
            sales_history_qs = sales_history_qs.filter(refund_status='full')

    # Paginate
    history_paginator = Paginator(sales_history_qs, 20)
    history_page = request.GET.get('history_page', 1)
    history_page_obj = history_paginator.get_page(history_page)
    active_tab = 'sales-tab'  # default
    if any([start_date, end_date, customer, item_name, refund_status]):
        active_tab = 'history-tab'

    return render(
        request,
        'sales_dashboard.html',
        {
            'inventory_items': inventory_items,
            'sales_orders': sales_orders,
            'total_sales': total_sales,
            'total_quantity_sold': total_quantity_sold,
            'daily_summary': daily_summary,
            'weekly_summary': weekly_summary,
            'monthly_summary': monthly_summary,
            'category_performance': category_performance,
            'category_chart_data': category_chart_data,
            'page_obj': page_obj,
            'paginator': paginator,
            'show_pagination': show_pagination,
            'peak_hour': peak_hour,
            'total_revenue': total_revenue,
            'total_profit': total_profit,
            'modules': MANAGEMENT_MODULES,
            'refund_history': refund_history,
            'active_tab': active_tab,
            'sales_history_page_obj': history_page_obj,
            'category_chart_data': category_chart_data,
        },
    )


@login_required
def sales_receipt(request, order_id):
    order = get_object_or_404(
        SalesOrder.objects.select_related('inventory_item'),
        pk=order_id,
    )
    return render(
        request,
        'sales_receipt.html',
        {
            'order': order,
            'company_name': 'VERSATEC Industrial Corporation',
        },
    )


import logging

logger = logging.getLogger(__name__)


@login_required
@require_POST
def save_quotation(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    def parse_date(value):
        try:
            return datetime.fromisoformat(value).date() if value else None
        except (ValueError, TypeError):
            return None

    try:
        # Create the Quotation
        quotation = Quotation.objects.create(
            quotation_number=payload.get("quotation_number", "").strip() or "UNNAMED",
            quotation_date=parse_date(payload.get("quotation_date")),
            valid_until=parse_date(payload.get("valid_until")),
            currency=payload.get("currency", "PHP") or "PHP",
            currency_other=payload.get("currency_other", "").strip(),
            customer_company=payload.get("customer", {}).get("company", "").strip(),
            customer_contact=payload.get("customer", {}).get("contact", "").strip(),
            customer_address=payload.get("customer", {}).get("address", "").strip(),
            customer_email=payload.get("customer", {}).get("email", "").strip(),
            customer_phone=payload.get("customer", {}).get("phone", "").strip(),
            payment_terms=payload.get("payment_terms", "").strip(),
            delivery_terms=payload.get("delivery_terms", "").strip(),
            warranty=payload.get("warranty", "").strip(),
            other_terms=payload.get("other_terms", "").strip(),
            subtotal=Decimal(payload.get("subtotal") or "0"),
            tax=Decimal(payload.get("tax") or "0"),
            discount=Decimal(payload.get("discount") or "0"),
            shipping=Decimal(payload.get("shipping") or "0"),
            grand_total=Decimal(payload.get("grand_total") or "0"),
            prepared_name=payload.get("prepared_by", {}).get("name", "").strip(),
            prepared_title=payload.get("prepared_by", {}).get("title", "").strip(),
            prepared_signature=payload.get("prepared_by", {})
            .get("signature", "")
            .strip(),
            prepared_date=parse_date(payload.get("prepared_by", {}).get("date")),
            approved_signature=payload.get("approved_by", {})
            .get("signature", "")
            .strip(),
            approved_date=parse_date(payload.get("approved_by", {}).get("date")),
        )

        # Create lines
        items = payload.get("items", []) or []
        for item in items:
            try:
                item_number = int(item.get("no") or 0)
            except (TypeError, ValueError):
                item_number = 0

            QuotationLine.objects.create(
                quotation=quotation,
                item_number=item_number,
                product_description=item.get("description", "").strip(),
                quantity=max(int(item.get("qty") or 0), 0),
                unit=item.get("unit", "").strip(),
                unit_price=Decimal(item.get("unit_price") or "0"),
                total_amount=Decimal(item.get("total") or "0"),
            )

        # Build download URL
        download_url = reverse("download_quotation_pdf", args=[quotation.id])
        return JsonResponse({"id": quotation.id, "download_url": download_url})

    except Exception as e:
        # Log the full traceback (check your console)
        logger.exception("save_quotation error")
        # Return a JSON error with the exact message
        return JsonResponse(
            {"error": str(e), "traceback": traceback.format_exc()},
            status=500,
        )


@login_required
def download_quotation_pdf(request, quotation_id):
    from .po_pdf import build_quotation_pdf

    quotation = get_object_or_404(Quotation, pk=quotation_id)
    lines = quotation.lines.all()
    generated_date = timezone.localtime(timezone.now())
    total_amount = quotation.grand_total
    company_name = "VERSATEC Industrial Corporation"

    pdf_bytes = build_quotation_pdf(
        quotation, lines, total_amount, generated_date, company_name
    )
    safe_name = "".join(
        ch if ch.isalnum() or ch in "-_" else "_"
        for ch in (quotation.quotation_number or "quotation")
    )
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{safe_name}.pdf"'
    return response



@require_dashboard('inventory_dashboard')
def inventory_dashboard(request):
    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
        item_id = request.POST.get('itemId', '').strip()
        name = request.POST.get('itemName', '').strip()

        if action == 'delete' and item_id:
            password = request.POST.get('password', '')
            if not password:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'error': 'Password is required to delete an item.'}, status=400)
                messages.error(request, 'Password is required to delete an item.')
                return redirect('inventory_dashboard')
            
            user = request.user
            if not user.check_password(password):
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'error': 'Incorrect password.'}, status=400)
                messages.error(request, "Incorrect password. Item not deleted.")
                return redirect("inventory_dashboard")
            
            deleted_count, _ = InventoryItem.objects.filter(pk=item_id).delete()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'deleted': bool(deleted_count)})
            messages.success(request, "Item deleted successfully.")
            return redirect('inventory_dashboard')
        
        if action == 'add_delivery':
            delivery_date = request.POST.get('delivery_date')
            driver = request.POST.get('driver', '').strip()
            delivered_from = request.POST.get('delivered_from', '').strip()
            delivered_to = request.POST.get('delivered_to', '').strip()

            if not delivery_date or not driver or not delivered_from or not delivered_to:
                messages.error(request, 'All delivery header fields are required.')
                return redirect('inventory_dashboard')
            
            delivery = Delivery.objects.create(
                delivery_date=delivery_date,
                driver=driver,
                delivered_from=delivered_from,
                delivered_to=delivered_to,
            )

            item_types = request.POST.getlist('item_type[]')
            quantities = request.POST.getlist('quantity_cartons[]')
            pcs_list = request.POST.getlist('pcs_per_carton[]')
            costs = request.POST.getlist('cost_per_carton[]')

            created = 0
            for i in range(len(item_types)):
                item_type = item_types[i].strip()
                try:
                    qty = int(quantities[i]) if i < len(quantities) else 0
                    pcs = int(pcs_list[i]) if i < len(pcs_list) else 0
                    cost = Decimal(costs[i]) if i < len(costs) else Decimal('0')
                except (ValueError, TypeError):
                    continue

                if item_type and qty > 0 and pcs > 0 and cost >= 0:
                    DeliveryLine.objects.create(
                        delivery=delivery,
                        item_type=item_type,
                        quantity_cartons=qty,
                        pcs_per_carton = pcs,
                        cost_per_carton=cost,
                    )

                    created += 1
            if created == 0:
                delivery.delete()
                messages.error(request, 'No valid items added. Delivery not saved.')
            else:
                messages.success(request, f"Delivery recorded with {created} items.")

            return redirect('inventory_dashboard')

        if name:
            if item_id:
                item = InventoryItem.objects.get(pk=item_id)
            else:
                item = InventoryItem()

            item.product_code = request.POST.get('productCode', '').strip()
            item.name = name
            # handle uploaded picture file
            if request.FILES.get('picture'):
                item.picture = request.FILES.get('picture')
                item.size = request.POST.get('size', '').strip()
                item.stock_available = int(request.POST.get('stockAvailable', 0) or 0)
                item.pcs_per_ctn = int(request.POST.get('pcsPerCtn', 0) or 0)
                item.carton_size = request.POST.get('cartonSize', '').strip()
                item.net_weight = Decimal(request.POST.get('netWeight', '0') or '0')
                item.gross_weight = Decimal(request.POST.get('grossWeight', '0') or '0')
                item.price = Decimal(request.POST.get('price', '0') or '0')
                item.description = request.POST.get('description', '').strip()
                item.save()

        return redirect('inventory_dashboard')

    inventory_items = InventoryItem.objects.all().order_by('-created_at')
    inventory_items_json = [
        {
            'id': item.id,
            'productCode': item.product_code,
            'name': item.name,
            'picture': item.picture.url if getattr(item, 'picture') else '',
            'size': item.size,
            'stockAvailable': item.stock_available,
            'pcsPerCtn': item.pcs_per_ctn,
            'cartonSize': item.carton_size,
            'netWeight': float(item.net_weight),
            'grossWeight': float(item.gross_weight),
            'price': float(item.price),
            'description': item.description,
        }
        for item in inventory_items
    ]

    deliveries = Delivery.objects.prefetch_related('lines').order_by('-delivery_date')

    return render(
        request,
        'inventory_dashboard.html',
        {
            'inventory_items': inventory_items,
            'inventory_items_json': inventory_items_json,
            'inventory_item_options': INVENTORY_ITEM_OPTIONS,
            'deliveries': deliveries,
            'total_stock': sum(item.stock_available for item in inventory_items),
            'low_stock_count': sum(1 for item in inventory_items if item.stock_available < 10),
            'modules': MANAGEMENT_MODULES,
        },
    )


@require_dashboard('payroll_dashboard')
def payroll_dashboard(request):
    if request.method == 'POST':
        action = request.POST.get('action', '').strip()

        # ---------- CREATE PAY RUN ----------
        if action == 'create_payrun':
            pay_period_id = request.POST.get('pay_period_id')
            if pay_period_id:
                try:
                    pay_period = PayPeriod.objects.get(pk=pay_period_id)
                    if pay_period.is_closed:
                        messages.error(request, 'Pay period is closed.')
                    else:
                        # Check if a run already exists for this period
                        existing = PayrollRun.objects.filter(pay_period=pay_period).first()
                        if existing:
                            messages.warning(request, f'A payroll run already exists for this period (ID {existing.id}).')
                        else:
                            run = PayrollRun.objects.create(
                                pay_period=pay_period,
                                cutoff_start=pay_period.start_date,
                                cutoff_end=pay_period.end_date,
                                status='draft'
                            )
                            messages.success(request, f'Payroll run #{run.id} created. Click "Compute" to calculate.')
                except PayPeriod.DoesNotExist:
                    messages.error(request, 'Invalid pay period.')
            return redirect('payroll_dashboard')

        if action == 'compute_payroll':
            run_id = request.POST.get('run_id')
            if run_id:
                try:
                    run = PayrollRun.objects.get(pk=run_id)
                    if run.status != 'draft':
                        messages.warning(request, 'Only draft runs can be computed.')
                    else:
                        employees = Employee.objects.filter(
                            Q(termination_date__isnull=True) | Q(termination_date__gt=run.cutoff_end)
                        )
                        # We'll use the helper functions (import them)
                        from .payroll_calculator import (
                            get_effective_shift_schedule,
                            get_attendance_for_period,
                            compute_daily_hours,
                            get_tax,
                            get_statutory_deductions,
                            get_voluntary_deductions
                        )

                        for emp in employees:
                            # 1. Base salary (prorated if hire date > cutoff_start)
                            if emp.hire_date > run.cutoff_start:
                                # count working days in period (excluding weekends and holidays)
                                # simplified: we'll compute days worked as difference in days
                                days_in_period = (run.cutoff_end - run.cutoff_start).days + 1
                                # get working days (exclude Sat/Sun) - we'll skip for now
                                # just use a simple ratio
                                working_days_in_month = 22  # approximate
                                days_worked = (run.cutoff_end - max(emp.hire_date, run.cutoff_start)).days + 1
                                if days_worked < 0:
                                    days_worked = 0
                                prorated = Decimal(days_worked) / Decimal(working_days_in_month)
                                base_pay = emp.base_salary * prorated
                            else:
                                # full period
                                if emp.salary_frequency == 'monthly':
                                    base_pay = emp.base_salary
                                else:  # semi-monthly
                                    base_pay = emp.base_salary * Decimal('0.5')  # per cut-off

                            # 2. Attendance logs & shift schedule
                            logs = get_attendance_for_period(emp, run.cutoff_start, run.cutoff_end)
                            total_regular = Decimal('0')
                            total_overtime = Decimal('0')
                            holiday_pay = Decimal('0')

                            for log in logs:
                                shift = get_effective_shift_schedule(emp, log.date)
                                if shift:
                                    regular, overtime = compute_daily_hours(log, shift)
                                    total_regular += regular
                                    total_overtime += overtime
                                # check if holiday
                                if Holiday.objects.filter(date=log.date).exists():
                                    # if worked on holiday, pay 200% of base day rate
                                    # we'll add holiday_pay later
                                    pass

                            # Compute overtime pay (assume 125% of base rate)
                            # Base rate per hour = base_pay / (working days * 8 hours)
                            # Simplified: use base_pay / 22 / 8
                            hourly_rate = base_pay / Decimal('22') / Decimal('8')
                            overtime_pay = total_overtime * hourly_rate * Decimal('1.25')

                            # 3. Gross pay
                            gross_pay = base_pay + overtime_pay + holiday_pay

                            # 4. Deductions
                            tax = get_tax(emp, gross_pay, run.cutoff_end)
                            statutory = get_statutory_deductions(emp, gross_pay, run.cutoff_end)
                            voluntary = get_voluntary_deductions(emp, run.cutoff_start, run.cutoff_end)
                            total_deductions = tax + statutory + voluntary

                            net_pay = gross_pay - total_deductions

                            # Create PayrollLine
                            PayrollLine.objects.create(
                                payroll_run=run,
                                employee=emp,
                                gross_pay=gross_pay,
                                total_deductions=total_deductions,
                                net_pay=net_pay,
                                breakdown={
                                    'base_pay': float(base_pay),
                                    'overtime_pay': float(overtime_pay),
                                    'holiday_pay': float(holiday_pay),
                                    'regular_hours': float(total_regular),
                                    'overtime_hours': float(total_overtime),
                                    'tax': float(tax),
                                    'statutory': float(statutory),
                                    'voluntary': float(voluntary),
                                },
                                regular_hours=total_regular,
                                overtime_hours=total_overtime,
                                holiday_pay=holiday_pay,
                            )

                        run.status = 'computed'
                        run.save()
                        messages.success(request, f'Payroll run #{run.id} computed successfully.')
                except PayrollRun.DoesNotExist:
                    messages.error(request, 'Run not found.')
            return redirect('payroll_dashboard')

        # ---------- APPROVE PAYROLL ----------
        if action == 'approve_payroll':
            run_id = request.POST.get('run_id')
            if run_id:
                try:
                    run = PayrollRun.objects.get(pk=run_id)
                    if run.status != 'computed':
                        messages.warning(request, 'Only computed runs can be approved.')
                    else:
                        run.status = 'approved'
                        run.save()
                        messages.success(request, f'Payroll run #{run.id} approved.')
                except PayrollRun.DoesNotExist:
                    messages.error(request, 'Run not found.')
            return redirect('payroll_dashboard')

        # ---------- DISBURSE PAYROLL ----------
        if action == 'disburse_payroll':
            run_id = request.POST.get('run_id')
            if run_id:
                try:
                    run = PayrollRun.objects.get(pk=run_id)
                    if run.status != 'approved':
                        messages.warning(request, 'Only approved runs can be disbursed.')
                    else:
                        # In real scenario, generate bank file and send payslips
                        run.status = 'disbursed'
                        run.save()
                        messages.success(request, f'Payroll run #{run.id} disbursed.')
                except PayrollRun.DoesNotExist:
                    messages.error(request, 'Run not found.')
            return redirect('payroll_dashboard')

        # ---------- ADD DEDUCTION CONFIG ----------
        if action == 'add_deduction':
            code = request.POST.get('code', '').strip()
            name = request.POST.get('name', '').strip()
            ded_type = request.POST.get('ded_type', 'voluntary')
            fixed_amount = request.POST.get('fixed_amount', '0')
            percentage = request.POST.get('percentage', '0')
            effective = request.POST.get('effective_date')
            try:
                fixed = Decimal(fixed_amount)
                pct = Decimal(percentage)
                if not code or not name or not effective:
                    messages.error(request, 'Code, name, and effective date are required.')
                else:
                    DeductionConfig.objects.create(
                        code=code,
                        name=name,
                        type=ded_type,
                        fixed_amount=fixed,
                        percentage_of_gross=pct,
                        effective_date=effective,
                        is_active=True
                    )
                    messages.success(request, 'Deduction configuration added.')
            except Exception as e:
                messages.error(request, f'Error: {e}')
            return redirect('payroll_dashboard')

        # ---------- ASSIGN DEDUCTION TO EMPLOYEE ----------
        if action == 'assign_deduction':
            employee_id = request.POST.get('employee_id')
            config_id = request.POST.get('config_id')
            amount = request.POST.get('amount', '0')
            start = request.POST.get('start_date')
            end = request.POST.get('end_date', '')
            total_remaining = request.POST.get('total_remaining', '0')
            try:
                emp = Employee.objects.get(pk=employee_id)
                config = DeductionConfig.objects.get(pk=config_id)
                EmployeeDeduction.objects.create(
                    employee=emp,
                    deduction_config=config,
                    amount=Decimal(amount),
                    start_date=start,
                    end_date=end or None,
                    total_remaining=Decimal(total_remaining)
                )
                messages.success(request, 'Deduction assigned.')
            except Exception as e:
                messages.error(request, f'Error: {e}')
            return redirect('payroll_dashboard')

        # ---------- DELETE PAYROLL RUN ----------
        if action == 'delete_run':
            run_id = request.POST.get('run_id')
            if run_id:
                try:
                    run = PayrollRun.objects.get(pk=run_id)
                    if run.status == 'draft':
                        run.delete()
                        messages.success(request, 'Payroll run deleted.')
                    else:
                        messages.warning(request, 'Cannot delete a run that is not in draft status.')
                except PayrollRun.DoesNotExist:
                    messages.error(request, 'Run not found.')
            return redirect('payroll_dashboard')

        # ---------- CLOSE PAY PERIOD ----------
        if action == 'close_period':
            period_id = request.POST.get('period_id')
            if period_id:
                try:
                    period = PayPeriod.objects.get(pk=period_id)
                    period.is_closed = True
                    period.save()
                    messages.success(request, 'Pay period closed.')
                except PayPeriod.DoesNotExist:
                    messages.error(request, 'Period not found.')
            return redirect('payroll_dashboard')

        # fallback
        return redirect('payroll_dashboard')

    # ----- GET request: gather data for the dashboard -----

    # Pay periods
    pay_periods = PayPeriod.objects.all().order_by('-start_date')

    # Payroll runs with aggregated counts
    runs = PayrollRun.objects.select_related('pay_period').annotate(
        employee_count=Count('lines', distinct=True),
        total_gross=Sum('lines__gross_pay'),
        total_net=Sum('lines__net_pay'),
    ).order_by('-created_at')

    # Deduction configs
    deduction_configs = DeductionConfig.objects.filter(is_active=True)

    # Employees for assigning deductions
    employees = Employee.objects.all().order_by('last_name', 'first_name')

    # Deductions assigned to employees (with employee and config prefetch)
    assigned_deductions = EmployeeDeduction.objects.select_related('employee', 'deduction_config').all()

    # Tax brackets (for display)
    tax_brackets = TaxBracket.objects.filter(tax_type='withholding').order_by('effective_date', 'min_amount')

    context = {
        'modules': MANAGEMENT_MODULES,
        'pay_periods': pay_periods,
        'runs': runs,
        'deduction_configs': deduction_configs,
        'employees': employees,
        'assigned_deductions': assigned_deductions,
        'tax_brackets': tax_brackets,
    }
    return render(request, 'payroll_dashboard.html', context)

def get_effective_shift_schedule(employee, date):
    """Get the shift schedule active on a given date."""
    shifts = employee.shift_schedules.filter(
        effective_date__lte=date,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=date)
    ).order_by('-effective_date')
    return shifts.first()

def get_attendance_for_period(employee, start_date, end_date):
    """Return attendance logs for the given period."""
    return employee.attendance_logs.filter(
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')

def compute_daily_hours(log, shift):
    """Compute regular and overtime hours for a single day."""
    if not log.clock_in or not log.clock_out:
        return Decimal('0'), Decimal('0')  # no hours if missing

    # Convert to datetime for calculation
    start = datetime.combine(log.date, log.clock_in)
    end = datetime.combine(log.date, log.clock_out)
    if end < start:  # e.g., overnight shift
        end += timedelta(days=1)

    total_hours = (end - start).total_seconds() / 3600

    # subtract break time
    if log.break_start and log.break_end:
        break_start = datetime.combine(log.date, log.break_start)
        break_end = datetime.combine(log.date, log.break_end)
        if break_end < break_start:
            break_end += timedelta(days=1)
        break_hours = (break_end - break_start).total_seconds() / 3600
    else:
        break_hours = 0

    worked_hours = total_hours - break_hours

    # Shift hours
    shift_start = datetime.combine(log.date, shift.start_time)
    shift_end = datetime.combine(log.date, shift.end_time)
    if shift_end < shift_start:
        shift_end += timedelta(days=1)
    shift_hours = (shift_end - shift_start).total_seconds() / 3600

    # Regular hours = min(worked_hours, shift_hours)
    regular_hours = min(worked_hours, shift_hours)
    overtime_hours = max(worked_hours - shift_hours, Decimal('0'))

    # Night differential: hours between 10 PM and 6 AM
    # For simplicity, we'll skip detailed night diff for now
    return Decimal(str(regular_hours)), Decimal(str(overtime_hours))

def get_tax(employee, gross_pay, cutoff_date):
    """Calculate withholding tax based on effective tax brackets."""
    # Get the latest tax bracket effective on or before cutoff_date
    bracket = TaxBracket.objects.filter(
        tax_type='withholding',
        effective_date__lte=cutoff_date
    ).order_by('-effective_date').first()
    if not bracket:
        return Decimal('0')

    brackets = TaxBracket.objects.filter(
        tax_type='withholding',
        effective_date__lte=cutoff_date
    ).order_by('effective_date', 'min_amount')
    if not brackets.exists():
        return Decimal('0')

    latest = brackets.last()
    return gross_pay * latest.tax_rate

def get_statutory_deductions(employee, gross_pay, cutoff_date):
    """Calculate SSS, PhilHealth, Pag-IBIG based on effective tables."""
    # Get effective rates for each type
    sss_bracket = TaxBracket.objects.filter(
        tax_type='sss',
        effective_date__lte=cutoff_date
    ).order_by('-effective_date').first()
    philhealth = TaxBracket.objects.filter(
        tax_type='philhealth',
        effective_date__lte=cutoff_date
    ).order_by('-effective_date').first()
    pagibig = TaxBracket.objects.filter(
        tax_type='pagibig',
        effective_date__lte=cutoff_date
    ).order_by('-effective_date').first()

    total = Decimal('0')
    if sss_bracket:
        total += gross_pay * sss_bracket.tax_rate
    if philhealth:
        total += gross_pay * philhealth.tax_rate
    if pagibig:
        total += gross_pay * pagibig.tax_rate
    return total

def get_voluntary_deductions(employee, cutoff_start, cutoff_end):
    """Get active voluntary/loan deductions for the employee."""
    deductions = EmployeeDeduction.objects.filter(
        employee=employee,
        start_date__lte=cutoff_end,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=cutoff_start)
    )
    total = Decimal('0')
    for ded in deductions:
        total += ded.amount
    return total


@login_required
@require_POST
def purchase_order_pdf(request):
    """Generate a Long Bond (8.5×13) Purchase Order PDF via ReportLab."""
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    try:
        pdf_bytes = build_purchase_order_pdf(payload)
    except Exception as exc:
        return JsonResponse({'error': f'Could not generate PDF: {exc}'}, status=500)

    po_number = (payload.get('po_number') or 'purchase-order').strip()
    safe_name = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in po_number) or 'purchase-order'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{safe_name}.pdf"'
    return response

@require_dashboard('accounting_dashboard')
def accounting_dashboard(request):
    return render(
        request,
        'accounting_dashboard.html',
        {
            'modules': MANAGEMENT_MODULES,
        },
    )

@require_dashboard('services_dashboard')
def services_dashboard(request):
    return render(
        request,
        'services_dashboard.html',
        {
            'modules': MANAGEMENT_MODULES,
            'repair_reports': ServiceRepairReport.objects.all()[:8],
            'job_orders': JobOrder.objects.all()[:8],
            'repair_report_count': ServiceRepairReport.objects.count(),
            'job_order_count': JobOrder.objects.count(),
        }
    )


@login_required
@require_POST
def create_service_repair_report(request):
    required = ('report_number', 'report_date', 'customer_name', 'equipment', 'complaint')
    if not all(request.POST.get(field, '').strip() for field in required):
        messages.error(request, 'Please complete all required Service Repair Report fields.')
        return redirect('services_dashboard')
    try:
        ServiceRepairReport.objects.create(
            report_number=request.POST['report_number'].strip(), report_date=request.POST['report_date'],
            customer_name=request.POST['customer_name'].strip(), contact_person=request.POST.get('contact_person', '').strip(),
            contact_number=request.POST.get('contact_number', '').strip(), customer_address=request.POST.get('customer_address', '').strip(),
            equipment=request.POST['equipment'].strip(), model_number=request.POST.get('model_number', '').strip(),
            serial_number=request.POST.get('serial_number', '').strip(), complaint=request.POST['complaint'].strip(),
            diagnosis=request.POST.get('diagnosis', '').strip(), repairs_performed=request.POST.get('repairs_performed', '').strip(),
            parts_used=request.POST.get('parts_used', '').strip(), technician=request.POST.get('technician', '').strip(),
            status=request.POST.get('status', 'open'), recommendations=request.POST.get('recommendations', '').strip(),
        )
        messages.success(request, 'Service Repair Report saved successfully.')
    except Exception as exc:
        messages.error(request, f'Could not save report: {exc}')
    return redirect('services_dashboard')


@login_required
@require_POST
def create_job_order(request):
    required = ('job_order_number', 'job_date', 'customer_name', 'scope_of_work')
    if not all(request.POST.get(field, '').strip() for field in required):
        messages.error(request, 'Please complete all required Job Order fields.')
        return redirect('services_dashboard')
    try:
        JobOrder.objects.create(
            job_order_number=request.POST['job_order_number'].strip(), job_date=request.POST['job_date'],
            customer_name=request.POST['customer_name'].strip(), contact_person=request.POST.get('contact_person', '').strip(),
            contact_number=request.POST.get('contact_number', '').strip(), service_location=request.POST.get('service_location', '').strip(),
            scope_of_work=request.POST['scope_of_work'].strip(), assigned_to=request.POST.get('assigned_to', '').strip(),
            scheduled_date=request.POST.get('scheduled_date') or None, priority=request.POST.get('priority', 'normal'),
            status=request.POST.get('status', 'open'), notes=request.POST.get('notes', '').strip(),
        )
        messages.success(request, 'Job Order saved successfully.')
    except Exception as exc:
        messages.error(request, f'Could not save job order: {exc}')
    return redirect('services_dashboard')


SERVICE_FIELD_LABELS = {
    'repair': [('Report No.', 'report_number'), ('Report Date', 'report_date'), ('Customer / Company', 'customer_name'),
               ('Contact Person', 'contact_person'), ('Contact Number', 'contact_number'), ('Customer Address', 'customer_address'),
               ('Equipment / Unit', 'equipment'), ('Model No.', 'model_number'), ('Serial No.', 'serial_number'),
               ('Reported Complaint / Issue', 'complaint'), ('Diagnosis', 'diagnosis'), ('Repairs Performed', 'repairs_performed'),
               ('Parts / Materials Used', 'parts_used'), ('Technician', 'technician'), ('Status', 'get_status_display'),
               ('Recommendations', 'recommendations')],
    'job': [('Job Order No.', 'job_order_number'), ('Job Date', 'job_date'), ('Customer / Company', 'customer_name'),
            ('Contact Person', 'contact_person'), ('Contact Number', 'contact_number'), ('Service Location', 'service_location'),
            ('Scope of Work', 'scope_of_work'), ('Assigned To', 'assigned_to'), ('Scheduled Date', 'scheduled_date'),
            ('Priority', 'get_priority_display'), ('Status', 'get_status_display'), ('Notes / Special Instructions', 'notes')],
}


def _service_record_context(record, document_type):
    fields = []
    for label, attribute in SERVICE_FIELD_LABELS[document_type]:
        value = getattr(record, attribute)
        value = value() if callable(value) else value
        fields.append((label, value or '—'))
    return {'record': record, 'fields': fields, 'document_type': document_type}


@login_required
def view_service_repair_report(request, report_id):
    return render(request, 'service_document_detail.html', _service_record_context(
        get_object_or_404(ServiceRepairReport, pk=report_id), 'repair'))


@login_required
def edit_service_repair_report(request, report_id):
    report = get_object_or_404(ServiceRepairReport, pk=report_id)
    form = ServiceRepairReportForm(request.POST or None, instance=report)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Service Repair Report updated successfully.')
        return redirect('view_service_repair_report', report_id=report.id)
    return render(request, 'service_document_form.html', {'form': form, 'record': report, 'document_type': 'repair'})


@login_required
@require_POST
def delete_service_repair_report(request, report_id):
    get_object_or_404(ServiceRepairReport, pk=report_id).delete()
    messages.success(request, 'Service Repair Report deleted.')
    return redirect('services_dashboard')


@login_required
def view_job_order(request, order_id):
    return render(request, 'service_document_detail.html', _service_record_context(
        get_object_or_404(JobOrder, pk=order_id), 'job'))


@login_required
def edit_job_order(request, order_id):
    order = get_object_or_404(JobOrder, pk=order_id)
    form = JobOrderForm(request.POST or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Job Order updated successfully.')
        return redirect('view_job_order', order_id=order.id)
    return render(request, 'service_document_form.html', {'form': form, 'record': order, 'document_type': 'job'})


@login_required
@require_POST
def delete_job_order(request, order_id):
    get_object_or_404(JobOrder, pk=order_id).delete()
    messages.success(request, 'Job Order deleted.')
    return redirect('services_dashboard')
