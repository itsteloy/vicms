from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import wraps
from .models import InventoryItem, SalesOrder, HRDocument, Employee, Department, Position, PayPeriod, PayrollRun, PayrollLine, DeductionConfig, EmployeeDeduction,TaxBracket, AttendanceLog, ShiftSchedule, LeaveBalance, LeaveRequest, Holiday, RefundRecord, Delivery, DeliveryLine, Quotation, QuotationLine, ServiceQuotation, ServiceQuotationLine, ServiceRepairReport, JobOrder, MaterialBorrow, MaterialBorrowLine, OfficialBusinessForm, WorkspaceAccount, Account, JournalEntry, JournalEntryLine, BankAccount, BankTransaction, Customer, Invoice, InvoicePayment, Supplier, Bill, BillPayment, PayrollExpenseEntry, TaxDeadline
from . import accounting_engine
from . import accounting_reports
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
from django.utils.dateparse import parse_date
from .po_pdf import build_purchase_order_pdf
from .forms import EmployeeForm, JobOrderForm, MaterialBorrowForm, OfficialBusinessFormForm, ServiceRepairReportForm
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

        if action == 'create_department':
            name = request.POST.get('department_name', '').strip()
            if not name:
                messages.error(request, 'Department name is required.')
            elif Department.objects.filter(name__iexact=name).exists():
                messages.warning(request, f'Department "{name}" already exists.')
            else:
                Department.objects.create(name=name)
                messages.success(request, f'Department "{name}" created.')
            return redirect(f"{reverse('hr_dashboard')}?tab=employeesTab")

        if action == 'create_position':
            title = request.POST.get('position_title', '').strip()
            if not title:
                messages.error(request, 'Position title is required.')
            elif Position.objects.filter(title__iexact=title).exists():
                messages.warning(request, f'Position "{title}" already exists.')
            else:
                Position.objects.create(title=title)
                messages.success(request, f'Position "{title}" created.')
            return redirect(f"{reverse('hr_dashboard')}?tab=employeesTab")

        if action == 'create_employee':
            form = EmployeeForm(request.POST)
            if form.is_valid():
                form.save()
                employee = form.instance
                messages.success(
                    request,
                    f'Employee {employee.full_name} ({employee.employee_id}) added. They will appear in payroll compute.',
                )
            else:
                for field, errors in form.errors.items():
                    label = field.replace('_', ' ').title()
                    for error in errors:
                        messages.error(request, f'{label}: {error}')
            return redirect(f"{reverse('hr_dashboard')}?tab=employeesTab")

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
            return redirect(f"{reverse('hr_dashboard')}?tab=documentsTab")

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
            return redirect(f"{reverse('hr_dashboard')}?tab=documentsTab")

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
            return redirect(f"{reverse('hr_dashboard')}?tab=documentsTab")

        # Record / correct an attendance log (upsert per employee + date)
        if action == 'log_attendance':
            employee_id = request.POST.get('att_employee', '').strip()
            date_str = request.POST.get('att_date', '').strip()
            status_val = request.POST.get('att_status', 'present').strip()
            clock_in = request.POST.get('att_clock_in', '').strip() or None
            clock_out = request.POST.get('att_clock_out', '').strip() or None
            break_start = request.POST.get('att_break_start', '').strip() or None
            break_end = request.POST.get('att_break_end', '').strip() or None
            remarks = request.POST.get('att_remarks', '').strip()

            employee = Employee.objects.filter(pk=employee_id).first()
            parsed_date = parse_date(date_str) if date_str else None

            if not employee or not parsed_date:
                messages.error(request, 'Employee and date are required to log attendance.')
            elif status_val not in dict(AttendanceLog.STATUS_CHOICES):
                messages.error(request, 'Invalid attendance status.')
            else:
                if status_val != 'present':
                    clock_in = clock_out = break_start = break_end = None
                AttendanceLog.objects.update_or_create(
                    employee=employee,
                    date=parsed_date,
                    defaults={
                        'status': status_val,
                        'clock_in': clock_in,
                        'clock_out': clock_out,
                        'break_start': break_start,
                        'break_end': break_end,
                        'remarks': remarks,
                    },
                )
                messages.success(request, f'Attendance for {employee.full_name} on {parsed_date} saved.')
            return redirect(f"{reverse('hr_dashboard')}?tab=attendanceTab")

        # Remove an incorrect attendance log
        if action == 'delete_attendance':
            att_id = request.POST.get('attendance_id', '').strip()
            if att_id:
                AttendanceLog.objects.filter(pk=att_id).delete()
                messages.success(request, 'Attendance record removed.')
            return redirect(f"{reverse('hr_dashboard')}?tab=attendanceTab")

        # Submit a new leave request on behalf of an employee
        if action == 'create_leave_request':
            employee_id = request.POST.get('lr_employee', '').strip()
            leave_type = request.POST.get('lr_leave_type', '').strip()
            start_date = parse_date(request.POST.get('lr_start_date', '').strip())
            end_date = parse_date(request.POST.get('lr_end_date', '').strip())
            remarks = request.POST.get('lr_remarks', '').strip()

            employee = Employee.objects.filter(pk=employee_id).first()
            valid_types = dict(LeaveBalance.LEAVE_TYPES)

            if not employee or not start_date or not end_date:
                messages.error(request, 'Employee, start date, and end date are required.')
            elif leave_type not in valid_types:
                messages.error(request, 'Invalid leave type.')
            elif end_date < start_date:
                messages.error(request, 'End date cannot be before the start date.')
            else:
                days_requested = (end_date - start_date).days + 1
                LeaveRequest.objects.create(
                    employee=employee,
                    start_date=start_date,
                    end_date=end_date,
                    leave_type=leave_type,
                    days_requested=days_requested,
                    remarks=remarks,
                )
                messages.success(request, f'Leave request for {employee.full_name} submitted and pending approval.')
            return redirect(f"{reverse('hr_dashboard')}?tab=requestsTab")

        # Approve a pending leave request: mark AttendanceLog for each covered day and deduct balance
        if action == 'approve_leave_request':
            req_id = request.POST.get('request_id', '').strip()
            leave_request = LeaveRequest.objects.filter(pk=req_id, status='pending').select_related('employee').first()
            if not leave_request:
                messages.error(request, 'Leave request not found or already processed.')
            else:
                leave_request.status = 'approved'
                leave_request.approved_at = timezone.now()
                leave_request.save(update_fields=['status', 'approved_at'])

                day = leave_request.start_date
                while day <= leave_request.end_date:
                    AttendanceLog.objects.update_or_create(
                        employee=leave_request.employee,
                        date=day,
                        defaults={
                            'status': 'leave',
                            'clock_in': None,
                            'clock_out': None,
                            'break_start': None,
                            'break_end': None,
                            'remarks': f'{leave_request.get_leave_type_display()} approved',
                        },
                    )
                    day += timedelta(days=1)

                balance = LeaveBalance.objects.filter(employee=leave_request.employee, leave_type=leave_request.leave_type).first()
                if balance:
                    balance.used_credits = balance.used_credits + leave_request.days_requested
                    balance.save(update_fields=['used_credits'])

                messages.success(request, f'Leave request for {leave_request.employee.full_name} approved.')
            return redirect(f"{reverse('hr_dashboard')}?tab=requestsTab")

        # Reject a pending leave request
        if action == 'reject_leave_request':
            req_id = request.POST.get('request_id', '').strip()
            leave_request = LeaveRequest.objects.filter(pk=req_id, status='pending').first()
            if not leave_request:
                messages.error(request, 'Leave request not found or already processed.')
            else:
                leave_request.status = 'rejected'
                leave_request.approved_at = timezone.now()
                leave_request.save(update_fields=['status', 'approved_at'])
                messages.success(request, f'Leave request for {leave_request.employee.full_name} rejected.')
            return redirect(f"{reverse('hr_dashboard')}?tab=requestsTab")

        # Delete a leave request that has not been processed yet
        if action == 'delete_leave_request':
            req_id = request.POST.get('request_id', '').strip()
            LeaveRequest.objects.filter(pk=req_id, status='pending').delete()
            messages.success(request, 'Leave request deleted.')
            return redirect(f"{reverse('hr_dashboard')}?tab=requestsTab")

    employees = Employee.objects.select_related('department', 'position').order_by('last_name', 'first_name')
    active_employee_count = employees.filter(termination_date__isnull=True).count()
    documents = HRDocument.objects.all()

    # ── Attendance tab: optional filters (employee / date range), defaults to last 14 days ──
    att_employee_filter = request.GET.get('att_employee_filter', '').strip()
    att_date_from = parse_date(request.GET.get('att_date_from', '').strip()) if request.GET.get('att_date_from') else None
    att_date_to = parse_date(request.GET.get('att_date_to', '').strip()) if request.GET.get('att_date_to') else None

    today = timezone.localdate()
    if not att_date_from and not att_date_to:
        att_date_from = today - timedelta(days=13)
        att_date_to = today

    attendance_logs = AttendanceLog.objects.select_related('employee').order_by('-date', 'employee__last_name')
    if att_employee_filter:
        attendance_logs = attendance_logs.filter(employee_id=att_employee_filter)
    if att_date_from:
        attendance_logs = attendance_logs.filter(date__gte=att_date_from)
    if att_date_to:
        attendance_logs = attendance_logs.filter(date__lte=att_date_to)
    attendance_logs = attendance_logs[:200]

    today_logs = AttendanceLog.objects.filter(date=today)
    today_present = today_logs.filter(status='present').count()
    today_absent = today_logs.filter(status='absent').count()
    today_on_leave = today_logs.filter(status='leave').count()

    # ── Requests tab: leave requests ──
    leave_requests = LeaveRequest.objects.select_related('employee').order_by('-submitted_at')[:200]
    pending_leave_count = LeaveRequest.objects.filter(status='pending').count()

    return render(
        request,
        'hr_dashboard.html',
        {
            'modules': MANAGEMENT_MODULES,
            'documents': documents,
            'document_types': HRDocument.DOCUMENT_TYPES,
            'status_choices': HRDocument.STATUS_CHOICES,
            'employees': employees,
            'departments': Department.objects.order_by('name'),
            'positions': Position.objects.order_by('title'),
            'employee_count': employees.count(),
            'active_employee_count': active_employee_count,
            'employee_form': EmployeeForm(),
            'next_employee_id': Employee.generate_employee_id(),
            'attendance_logs': attendance_logs,
            'attendance_status_choices': AttendanceLog.STATUS_CHOICES,
            'att_employee_filter': att_employee_filter,
            'att_date_from': att_date_from,
            'att_date_to': att_date_to,
            'today': today,
            'today_present': today_present,
            'today_absent': today_absent,
            'today_on_leave': today_on_leave,
            'leave_requests': leave_requests,
            'leave_type_choices': LeaveBalance.LEAVE_TYPES,
            'pending_leave_count': pending_leave_count,
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

    recent_quotations = Quotation.objects.all()[:10]
    recent_service_quotations = ServiceQuotation.objects.all()[:10]

    return render(
        request,
        'sales_dashboard.html',
        {
            'inventory_items': inventory_items,
            'recent_quotations': recent_quotations,
            'recent_service_quotations': recent_service_quotations,
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
        grand_total = Decimal(payload.get("grand_total") or "0")
        initial_payment = Decimal(payload.get("initial_payment") or "0")
        balance_due = grand_total - initial_payment

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
            grand_total=grand_total,
            initial_payment=initial_payment,
            balance_due=balance_due,
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


@login_required
@require_POST
def save_service_quotation(request):
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
        grand_total = Decimal(payload.get("grand_total") or "0")
        initial_payment = Decimal(payload.get("initial_payment") or "0")
        balance_due = grand_total - initial_payment

        quotation = ServiceQuotation.objects.create(
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
            service_schedule=payload.get("service_schedule", "").strip(),
            warranty=payload.get("warranty", "").strip(),
            other_terms=payload.get("other_terms", "").strip(),
            subtotal=Decimal(payload.get("subtotal") or "0"),
            tax=Decimal(payload.get("tax") or "0"),
            discount=Decimal(payload.get("discount") or "0"),
            other_fees=Decimal(payload.get("other_fees") or "0"),
            grand_total=grand_total,
            initial_payment=initial_payment,
            balance_due=balance_due,
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

        items = payload.get("items", []) or []
        for item in items:
            try:
                item_number = int(item.get("no") or 0)
            except (TypeError, ValueError):
                item_number = 0

            ServiceQuotationLine.objects.create(
                service_quotation=quotation,
                item_number=item_number,
                service_description=item.get("description", "").strip(),
                quantity=max(int(item.get("qty") or 0), 0),
                unit=item.get("unit", "").strip(),
                unit_price=Decimal(item.get("unit_price") or "0"),
                total_amount=Decimal(item.get("total") or "0"),
            )

        download_url = reverse("download_service_quotation_pdf", args=[quotation.id])
        return JsonResponse({"id": quotation.id, "download_url": download_url})

    except Exception as e:
        logger.exception("save_service_quotation error")
        return JsonResponse(
            {"error": str(e), "traceback": traceback.format_exc()},
            status=500,
        )


@login_required
def download_service_quotation_pdf(request, quotation_id):
    from .po_pdf import build_service_quotation_pdf

    quotation = get_object_or_404(ServiceQuotation, pk=quotation_id)
    lines = quotation.lines.all()
    generated_date = timezone.localtime(timezone.now())
    total_amount = quotation.grand_total
    company_name = "VERSATEC Industrial Corporation"

    pdf_bytes = build_service_quotation_pdf(
        quotation, lines, total_amount, generated_date, company_name
    )
    safe_name = "".join(
        ch if ch.isalnum() or ch in "-_" else "_"
        for ch in (quotation.quotation_number or "service_quotation")
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

        # ---------- CREATE PAY PERIOD ----------
        if action == 'create_pay_period':
            start_date = request.POST.get('start_date', '').strip()
            end_date = request.POST.get('end_date', '').strip()
            pay_date = request.POST.get('pay_date', '').strip()
            period_type = request.POST.get('period_type', 'monthly').strip()

            if not all([start_date, end_date, pay_date]):
                messages.error(request, 'Start date, end date, and pay date are required.')
            else:
                try:
                    start = date.fromisoformat(start_date)
                    end = date.fromisoformat(end_date)
                    pay = date.fromisoformat(pay_date)
                    if end < start:
                        messages.error(request, 'End date must be on or after the start date.')
                    else:
                        if pay < end:
                            messages.warning(request, 'Pay date is before the period end date.')
                        period = PayPeriod.objects.create(
                            start_date=start,
                            end_date=end,
                            pay_date=pay,
                            period_type=period_type if period_type in ('monthly', 'semi-monthly') else 'monthly',
                        )
                        messages.success(
                            request,
                            f'Pay period {period.start_date} – {period.end_date} created. You can now create a pay run.',
                        )
                except ValueError:
                    messages.error(request, 'Invalid date format.')
                except Exception as exc:
                    messages.error(request, f'Could not create pay period: {exc}')
            return redirect(f"{reverse('payroll_dashboard')}?tab=payrunsTab")

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
            else:
                messages.error(request, 'Please select a pay period.')
            return redirect(f"{reverse('payroll_dashboard')}?tab=payrunsTab")

        if action == 'compute_payroll':
            run_id = request.POST.get('run_id')
            if run_id:
                try:
                    run = PayrollRun.objects.get(pk=run_id)
                    if run.status != 'draft':
                        messages.warning(request, 'Only draft runs can be computed.')
                    else:
                        from .payroll_calculator import (
                            compute_daily_hours,
                            get_attendance_for_period,
                            get_effective_shift_schedule,
                            get_statutory_deductions,
                            get_tax,
                            get_voluntary_deductions,
                        )

                        employees = Employee.objects.filter(
                            Q(termination_date__isnull=True) | Q(termination_date__gt=run.cutoff_end)
                        )
                        run.lines.all().delete()

                        computed_count = 0
                        for emp in employees:
                            if emp.hire_date > run.cutoff_end:
                                continue

                            if emp.hire_date > run.cutoff_start:
                                working_days_in_month = Decimal('22')
                                days_worked = (run.cutoff_end - max(emp.hire_date, run.cutoff_start)).days + 1
                                if days_worked < 0:
                                    days_worked = 0
                                prorated = Decimal(days_worked) / working_days_in_month
                                base_pay = emp.base_salary * prorated
                            elif emp.salary_frequency == 'monthly':
                                base_pay = emp.base_salary
                            else:
                                base_pay = emp.base_salary * Decimal('0.5')

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

                            hourly_rate = base_pay / Decimal('22') / Decimal('8')
                            overtime_pay = total_overtime * hourly_rate * Decimal('1.25')
                            gross_pay = base_pay + overtime_pay + holiday_pay

                            tax = get_tax(emp, gross_pay, run.cutoff_end)
                            statutory = get_statutory_deductions(emp, gross_pay, run.cutoff_end)
                            voluntary = get_voluntary_deductions(emp, run.cutoff_start, run.cutoff_end)
                            total_deductions = tax + statutory + voluntary
                            net_pay = gross_pay - total_deductions

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
                            computed_count += 1

                        run.status = 'computed'
                        run.save()
                        messages.success(
                            request,
                            f'Payroll run #{run.id} computed for {computed_count} employee(s).',
                        )
                except PayrollRun.DoesNotExist:
                    messages.error(request, 'Run not found.')
                except Exception as exc:
                    messages.error(request, f'Compute failed: {exc}')
            return redirect(f"{reverse('payroll_dashboard')}?tab=payrunsTab")

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
            return redirect(f"{reverse('payroll_dashboard')}?tab=approvalsTab")

        # ---------- DISBURSE PAYROLL ----------
        if action == 'disburse_payroll':
            run_id = request.POST.get('run_id')
            if run_id:
                try:
                    run = PayrollRun.objects.select_related('pay_period').get(pk=run_id)
                    if run.status != 'approved':
                        messages.warning(request, 'Only approved runs can be disbursed.')
                    else:
                        run.status = 'disbursed'
                        run.save()
                        period = run.pay_period
                        period.is_closed = True
                        period.save(update_fields=['is_closed'])
                        messages.success(
                            request,
                            f'Payroll run #{run.id} disbursed and pay period closed.',
                        )
                except PayrollRun.DoesNotExist:
                    messages.error(request, 'Run not found.')
            return redirect(f"{reverse('payroll_dashboard')}?tab=payrunsTab")

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
            return redirect(f"{reverse('payroll_dashboard')}?tab=deductionsTab")

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
            return redirect(f"{reverse('payroll_dashboard')}?tab=deductionsTab")

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
            return redirect(f"{reverse('payroll_dashboard')}?tab=payrunsTab")

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
            return redirect(f"{reverse('payroll_dashboard')}?tab=payrunsTab")

        # fallback
        return redirect(f"{reverse('payroll_dashboard')}?tab=payrunsTab")

    # ----- GET request: gather data for the dashboard -----

    # Pay periods
    pay_periods = PayPeriod.objects.all().order_by('-start_date')

    # Payroll runs with aggregated counts
    runs = PayrollRun.objects.select_related('pay_period').prefetch_related(
        'lines__employee',
    ).annotate(
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
    if request.method == 'POST':
        action = request.POST.get('action', '').strip()

        def parse_date(value):
            try:
                return date.fromisoformat(value) if value else None
            except ValueError:
                return None

        def parse_decimal(value, default='0'):
            try:
                return Decimal(value or default)
            except Exception:
                return Decimal(default)

        # ---------- CHART OF ACCOUNTS ----------
        if action == 'create_account':
            code = request.POST.get('code', '').strip()
            name = request.POST.get('name', '').strip()
            account_type = request.POST.get('account_type', '').strip()
            category = request.POST.get('category', 'other').strip()
            description = request.POST.get('description', '').strip()
            if not code or not name or not account_type:
                messages.error(request, 'Account code, name, and type are required.')
            elif Account.objects.filter(code=code).exists():
                messages.error(request, f'Account code "{code}" already exists.')
            else:
                Account.objects.create(
                    code=code, name=name, account_type=account_type,
                    category=category or 'other', description=description,
                )
                messages.success(request, f'Account "{code} – {name}" created.')
            return redirect(f"{reverse('accounting_dashboard')}?tab=journalTab")

        # ---------- CUSTOMERS ----------
        if action == 'create_customer':
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, 'Customer name is required.')
            else:
                Customer.objects.create(
                    name=name,
                    contact_person=request.POST.get('contact_person', '').strip(),
                    phone=request.POST.get('phone', '').strip(),
                    email=request.POST.get('email', '').strip(),
                    address=request.POST.get('address', '').strip(),
                    tax_id=request.POST.get('tax_id', '').strip(),
                )
                messages.success(request, f'Customer "{name}" added.')
            return redirect(f"{reverse('accounting_dashboard')}?tab=arTab")

        # ---------- INVOICES (AR) ----------
        if action == 'create_invoice':
            customer_id = request.POST.get('customer_id')
            revenue_account_id = request.POST.get('revenue_account_id')
            invoice_date = parse_date(request.POST.get('invoice_date'))
            amount = parse_decimal(request.POST.get('amount'))
            try:
                if not customer_id or not revenue_account_id or not invoice_date or amount <= 0:
                    messages.error(request, 'Customer, revenue account, invoice date, and a positive amount are required.')
                else:
                    customer = Customer.objects.get(pk=customer_id)
                    revenue_account = Account.objects.get(pk=revenue_account_id)
                    invoice = Invoice.objects.create(
                        invoice_number=request.POST.get('invoice_number', '').strip() or f'INV-{timezone.now().strftime("%Y%m%d%H%M%S")}',
                        customer=customer,
                        invoice_date=invoice_date,
                        due_date=parse_date(request.POST.get('due_date')),
                        amount=amount,
                        revenue_account=revenue_account,
                        notes=request.POST.get('notes', '').strip(),
                    )
                    accounting_engine.post_invoice(invoice, user=request.user)
                    messages.success(request, f'Invoice {invoice.invoice_number} recorded and posted to the ledger.')
            except (Customer.DoesNotExist, Account.DoesNotExist):
                messages.error(request, 'Invalid customer or revenue account.')
            except accounting_engine.UnbalancedEntryError as exc:
                messages.error(request, f'Could not post invoice: {exc}')
            return redirect(f"{reverse('accounting_dashboard')}?tab=arTab")

        if action == 'record_invoice_payment':
            invoice_id = request.POST.get('invoice_id')
            bank_account_id = request.POST.get('bank_account_id')
            amount = parse_decimal(request.POST.get('amount'))
            payment_date = parse_date(request.POST.get('payment_date'))
            try:
                if not invoice_id or not bank_account_id or not payment_date or amount <= 0:
                    messages.error(request, 'Invoice, bank account, date, and a positive amount are required.')
                else:
                    invoice = Invoice.objects.get(pk=invoice_id)
                    bank_account = BankAccount.objects.get(pk=bank_account_id)
                    if amount > invoice.balance_due:
                        messages.warning(request, 'Payment exceeds the remaining balance due; recording anyway.')
                    payment = InvoicePayment.objects.create(
                        invoice=invoice, payment_date=payment_date, amount=amount,
                        bank_account=bank_account, reference=request.POST.get('reference', '').strip(),
                    )
                    accounting_engine.post_invoice_payment(payment, user=request.user)
                    messages.success(request, f'Payment of ₱{amount:.2f} recorded against {invoice.invoice_number}.')
            except (Invoice.DoesNotExist, BankAccount.DoesNotExist):
                messages.error(request, 'Invalid invoice or bank account.')
            except accounting_engine.UnbalancedEntryError as exc:
                messages.error(request, f'Could not post payment: {exc}')
            return redirect(f"{reverse('accounting_dashboard')}?tab=arTab")

        # ---------- SUPPLIERS ----------
        if action == 'create_supplier':
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, 'Supplier name is required.')
            else:
                Supplier.objects.create(
                    name=name,
                    contact_person=request.POST.get('contact_person', '').strip(),
                    phone=request.POST.get('phone', '').strip(),
                    email=request.POST.get('email', '').strip(),
                    address=request.POST.get('address', '').strip(),
                    tax_id=request.POST.get('tax_id', '').strip(),
                    payment_terms=request.POST.get('payment_terms', '').strip(),
                )
                messages.success(request, f'Supplier "{name}" added.')
            return redirect(f"{reverse('accounting_dashboard')}?tab=apTab")

        # ---------- BILLS (AP) ----------
        if action == 'create_bill':
            supplier_id = request.POST.get('supplier_id')
            expense_account_id = request.POST.get('expense_account_id')
            bill_date = parse_date(request.POST.get('bill_date'))
            amount = parse_decimal(request.POST.get('amount'))
            try:
                if not supplier_id or not expense_account_id or not bill_date or amount <= 0:
                    messages.error(request, 'Supplier, expense account, bill date, and a positive amount are required.')
                else:
                    supplier = Supplier.objects.get(pk=supplier_id)
                    expense_account = Account.objects.get(pk=expense_account_id)
                    bill = Bill.objects.create(
                        bill_number=request.POST.get('bill_number', '').strip() or f'BILL-{timezone.now().strftime("%Y%m%d%H%M%S")}',
                        supplier=supplier,
                        bill_date=bill_date,
                        due_date=parse_date(request.POST.get('due_date')),
                        amount=amount,
                        expense_account=expense_account,
                        notes=request.POST.get('notes', '').strip(),
                    )
                    accounting_engine.post_bill(bill, user=request.user)
                    messages.success(request, f'Bill {bill.bill_number} recorded and posted to the ledger.')
            except (Supplier.DoesNotExist, Account.DoesNotExist):
                messages.error(request, 'Invalid supplier or expense account.')
            except accounting_engine.UnbalancedEntryError as exc:
                messages.error(request, f'Could not post bill: {exc}')
            return redirect(f"{reverse('accounting_dashboard')}?tab=apTab")

        if action == 'record_bill_payment':
            bill_id = request.POST.get('bill_id')
            bank_account_id = request.POST.get('bank_account_id')
            amount = parse_decimal(request.POST.get('amount'))
            payment_date = parse_date(request.POST.get('payment_date'))
            try:
                if not bill_id or not bank_account_id or not payment_date or amount <= 0:
                    messages.error(request, 'Bill, bank account, date, and a positive amount are required.')
                else:
                    bill = Bill.objects.get(pk=bill_id)
                    bank_account = BankAccount.objects.get(pk=bank_account_id)
                    if amount > bill.balance_due:
                        messages.warning(request, 'Payment exceeds the remaining balance due; recording anyway.')
                    payment = BillPayment.objects.create(
                        bill=bill, payment_date=payment_date, amount=amount,
                        bank_account=bank_account, reference=request.POST.get('reference', '').strip(),
                    )
                    accounting_engine.post_bill_payment(payment, user=request.user)
                    messages.success(request, f'Payment of ₱{amount:.2f} recorded against {bill.bill_number}.')
            except (Bill.DoesNotExist, BankAccount.DoesNotExist):
                messages.error(request, 'Invalid bill or bank account.')
            except accounting_engine.UnbalancedEntryError as exc:
                messages.error(request, f'Could not post payment: {exc}')
            return redirect(f"{reverse('accounting_dashboard')}?tab=apTab")

        # ---------- BANK & CASH ----------
        if action == 'create_bank_account':
            name = request.POST.get('name', '').strip()
            gl_account_id = request.POST.get('gl_account_id')
            try:
                if not name or not gl_account_id:
                    messages.error(request, 'Name and GL account are required.')
                else:
                    BankAccount.objects.create(
                        name=name,
                        account_type=request.POST.get('account_type', 'bank'),
                        bank_name=request.POST.get('bank_name', '').strip(),
                        account_number=request.POST.get('account_number', '').strip(),
                        gl_account=Account.objects.get(pk=gl_account_id),
                        opening_balance=parse_decimal(request.POST.get('opening_balance')),
                        opening_balance_date=parse_date(request.POST.get('opening_balance_date')),
                    )
                    messages.success(request, f'Bank/cash account "{name}" added.')
            except Account.DoesNotExist:
                messages.error(request, 'Invalid GL account.')
            return redirect(f"{reverse('accounting_dashboard')}?tab=bankTab")

        if action == 'record_bank_transaction':
            bank_account_id = request.POST.get('bank_account_id')
            transaction_type = request.POST.get('transaction_type', 'deposit')
            amount = parse_decimal(request.POST.get('amount'))
            transaction_date = parse_date(request.POST.get('transaction_date'))
            contra_account_id = request.POST.get('contra_account_id')
            to_bank_account_id = request.POST.get('to_bank_account_id')
            try:
                if not bank_account_id or not transaction_date or amount <= 0:
                    messages.error(request, 'Bank account, date, and a positive amount are required.')
                elif transaction_type in ('deposit', 'withdrawal') and not contra_account_id:
                    messages.error(request, 'Please select a contra account for this deposit/withdrawal.')
                elif transaction_type == 'transfer' and not to_bank_account_id:
                    messages.error(request, 'Please select a destination account for this transfer.')
                else:
                    txn = BankTransaction.objects.create(
                        bank_account=BankAccount.objects.get(pk=bank_account_id),
                        transaction_date=transaction_date,
                        transaction_type=transaction_type,
                        amount=amount,
                        contra_account=Account.objects.get(pk=contra_account_id) if contra_account_id else None,
                        to_bank_account=BankAccount.objects.get(pk=to_bank_account_id) if to_bank_account_id else None,
                        reference=request.POST.get('reference', '').strip(),
                        description=request.POST.get('description', '').strip(),
                    )
                    accounting_engine.post_bank_transaction(txn, user=request.user)
                    messages.success(request, f'{txn.get_transaction_type_display()} of ₱{amount:.2f} recorded.')
            except (BankAccount.DoesNotExist, Account.DoesNotExist):
                messages.error(request, 'Invalid bank account or contra account.')
            except accounting_engine.UnbalancedEntryError as exc:
                messages.error(request, f'Could not post transaction: {exc}')
            return redirect(f"{reverse('accounting_dashboard')}?tab=bankTab")

        # ---------- PAYROLL EXPENSE ----------
        if action == 'create_payroll_expense':
            entry_date = parse_date(request.POST.get('entry_date'))
            amount = parse_decimal(request.POST.get('amount'))
            bank_account_id = request.POST.get('bank_account_id')
            expense_account_id = request.POST.get('expense_account_id')
            try:
                if not entry_date or amount <= 0 or not bank_account_id or not expense_account_id:
                    messages.error(request, 'Date, amount, bank account, and expense account are required.')
                else:
                    entry_row = PayrollExpenseEntry.objects.create(
                        entry_date=entry_date,
                        description=request.POST.get('description', '').strip() or 'Payroll expense',
                        amount=amount,
                        bank_account=BankAccount.objects.get(pk=bank_account_id),
                        expense_account=Account.objects.get(pk=expense_account_id),
                    )
                    accounting_engine.post_payroll_expense(entry_row, user=request.user)
                    messages.success(request, f'Payroll expense of ₱{amount:.2f} recorded.')
            except (BankAccount.DoesNotExist, Account.DoesNotExist):
                messages.error(request, 'Invalid bank account or expense account.')
            except accounting_engine.UnbalancedEntryError as exc:
                messages.error(request, f'Could not post payroll expense: {exc}')
            return redirect(f"{reverse('accounting_dashboard')}?tab=payrollExpenseTab")

        # ---------- MANUAL JOURNAL ENTRY (simple POST form, up to 6 lines) ----------
        if action == 'create_journal_entry':
            entry_date = parse_date(request.POST.get('entry_date'))
            memo = request.POST.get('memo', '').strip()
            lines = []
            for i in range(1, 9):
                account_id = request.POST.get(f'line_account_{i}')
                if not account_id:
                    continue
                debit = parse_decimal(request.POST.get(f'line_debit_{i}'))
                credit = parse_decimal(request.POST.get(f'line_credit_{i}'))
                if debit <= 0 and credit <= 0:
                    continue
                try:
                    account = Account.objects.get(pk=account_id)
                except Account.DoesNotExist:
                    continue
                lines.append({
                    'account': account, 'debit': debit, 'credit': credit,
                    'description': request.POST.get(f'line_description_{i}', '').strip(),
                })
            try:
                if not entry_date:
                    messages.error(request, 'Entry date is required.')
                else:
                    accounting_engine.post_journal_entry(
                        entry_date=entry_date, memo=memo, source_type='manual',
                        lines=lines, user=request.user,
                    )
                    messages.success(request, 'Manual journal entry posted.')
            except accounting_engine.UnbalancedEntryError as exc:
                messages.error(request, f'Could not post journal entry: {exc}')
            return redirect(f"{reverse('accounting_dashboard')}?tab=journalTab")

        if action == 'void_journal_entry':
            entry_id = request.POST.get('entry_id')
            try:
                entry = JournalEntry.objects.get(pk=entry_id)
                if entry.is_void:
                    messages.warning(request, 'This entry is already void.')
                else:
                    accounting_engine.void_journal_entry(entry, user=request.user)
                    messages.success(request, f'Entry {entry.entry_number} voided with a reversing entry.')
            except JournalEntry.DoesNotExist:
                messages.error(request, 'Journal entry not found.')
            return redirect(f"{reverse('accounting_dashboard')}?tab=journalTab")

        # ---------- TAX DEADLINES ----------
        if action == 'create_tax_deadline':
            name = request.POST.get('name', '').strip()
            tax_type = request.POST.get('tax_type', '').strip()
            period_start = parse_date(request.POST.get('period_start'))
            period_end = parse_date(request.POST.get('period_end'))
            due_date = parse_date(request.POST.get('due_date'))
            if not all([name, tax_type, period_start, period_end, due_date]):
                messages.error(request, 'All fields are required for a tax deadline.')
            else:
                TaxDeadline.objects.create(
                    name=name, tax_type=tax_type, period_start=period_start,
                    period_end=period_end, due_date=due_date,
                    notes=request.POST.get('notes', '').strip(),
                )
                messages.success(request, f'Tax deadline "{name}" added.')
            return redirect(f"{reverse('accounting_dashboard')}?tab=taxTab")

        if action == 'mark_deadline_filed':
            deadline_id = request.POST.get('deadline_id')
            try:
                deadline = TaxDeadline.objects.get(pk=deadline_id)
                deadline.is_filed = True
                deadline.filed_date = date.today()
                deadline.save(update_fields=['is_filed', 'filed_date'])
                messages.success(request, f'"{deadline.name}" marked as filed.')
            except TaxDeadline.DoesNotExist:
                messages.error(request, 'Tax deadline not found.')
            return redirect(f"{reverse('accounting_dashboard')}?tab=taxTab")

        return redirect('accounting_dashboard')

    # ----- GET request: gather data for the dashboard -----
    today = date.today()

    # Recompute overdue statuses so lists/KPIs are always fresh.
    for invoice in Invoice.objects.filter(status__in=['unpaid', 'partial']):
        old_status = invoice.status
        invoice.refresh_status()
        if invoice.status != old_status:
            invoice.save(update_fields=['status'])
    for bill in Bill.objects.filter(status__in=['unpaid', 'partial']):
        old_status = bill.status
        bill.refresh_status()
        if bill.status != old_status:
            bill.save(update_fields=['status'])

    accounts = Account.objects.filter(is_active=True).order_by('code')
    revenue_accounts = accounts.filter(account_type='revenue')
    expense_accounts = accounts.filter(account_type='expense')

    customers = Customer.objects.filter(is_active=True).order_by('name')
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')
    bank_accounts = BankAccount.objects.filter(is_active=True).select_related('gl_account').order_by('name')
    cash_bank_gl_accounts = accounts.filter(category__in=['cash', 'bank'])

    invoices = Invoice.objects.select_related('customer', 'revenue_account').prefetch_related('payments')[:100]
    bills = Bill.objects.select_related('supplier', 'expense_account').prefetch_related('payments')[:100]
    payable_invoices = Invoice.objects.filter(status__in=['unpaid', 'partial', 'overdue']).select_related('customer')
    payable_bills = Bill.objects.filter(status__in=['unpaid', 'partial', 'overdue']).select_related('supplier')
    bank_transactions = BankTransaction.objects.select_related('bank_account', 'contra_account', 'to_bank_account')[:50]
    payroll_expenses = PayrollExpenseEntry.objects.select_related('bank_account', 'expense_account')[:50]
    journal_entries = JournalEntry.objects.select_related('created_by').prefetch_related('lines__account')[:80]
    tax_deadlines = TaxDeadline.objects.all().order_by('due_date')

    # ----- KPIs / notifications -----
    ar_total = sum((inv.balance_due for inv in Invoice.objects.filter(status__in=['unpaid', 'partial', 'overdue'])), Decimal('0'))
    ap_total = sum((b.balance_due for b in Bill.objects.filter(status__in=['unpaid', 'partial', 'overdue'])), Decimal('0'))
    cash_position = sum((acct.current_balance for acct in bank_accounts), Decimal('0'))

    overdue_invoices = [inv for inv in invoices if inv.status == 'overdue']
    overdue_bills = [b for b in bills if b.status == 'overdue']
    low_balance_accounts = [acct for acct in bank_accounts if acct.current_balance < Decimal('5000')]
    upcoming_deadlines = [d for d in tax_deadlines if not d.is_filed and d.due_date >= today][:6]
    overdue_deadlines = [d for d in tax_deadlines if d.is_overdue]

    month_start = today.replace(day=1)
    quarter_index = (today.month - 1) // 3
    quarter_start = today.replace(month=quarter_index * 3 + 1, day=1)

    monthly_income_statement = accounting_reports.income_statement(month_start, today)
    quarter_vat_summary = accounting_reports.vat_summary(quarter_start, today)

    # ----- Financial reports (Reports tab) -----
    report_type = request.GET.get('report_type', 'trial_balance')
    try:
        report_start = date.fromisoformat(request.GET.get('report_start') or '') 
    except ValueError:
        report_start = month_start
    try:
        report_end = date.fromisoformat(request.GET.get('report_end') or '')
    except ValueError:
        report_end = today
    report_account_id = request.GET.get('report_account_id')

    report_data = None
    report_account = None
    if report_type == 'trial_balance':
        report_data = accounting_reports.trial_balance(as_of_date=report_end)
    elif report_type == 'income_statement':
        report_data = accounting_reports.income_statement(report_start, report_end)
    elif report_type == 'balance_sheet':
        report_data = accounting_reports.balance_sheet(as_of_date=report_end)
    elif report_type == 'cash_flow':
        report_data = accounting_reports.cash_flow_statement(report_start, report_end)
    elif report_type == 'general_ledger' and report_account_id:
        report_account = accounts.filter(pk=report_account_id).first()
        if report_account:
            report_data = accounting_reports.general_ledger(report_account, report_start, report_end)

    context = {
        'modules': MANAGEMENT_MODULES,
        'today': today,
        'accounts': accounts,
        'revenue_accounts': revenue_accounts,
        'expense_accounts': expense_accounts,
        'customers': customers,
        'suppliers': suppliers,
        'bank_accounts': bank_accounts,
        'cash_bank_gl_accounts': cash_bank_gl_accounts,
        'invoices': invoices,
        'bills': bills,
        'payable_invoices': payable_invoices,
        'payable_bills': payable_bills,
        'bank_transactions': bank_transactions,
        'payroll_expenses': payroll_expenses,
        'journal_entries': journal_entries,
        'tax_deadlines': tax_deadlines,
        'upcoming_deadlines': upcoming_deadlines,
        'overdue_deadlines': overdue_deadlines,
        'ar_total': ar_total,
        'ap_total': ap_total,
        'cash_position': cash_position,
        'overdue_invoices': overdue_invoices,
        'overdue_bills': overdue_bills,
        'low_balance_accounts': low_balance_accounts,
        'monthly_income_statement': monthly_income_statement,
        'quarter_vat_summary': quarter_vat_summary,
        'quarter_start': quarter_start,
        'report_type': report_type,
        'report_start': report_start,
        'report_end': report_end,
        'report_data': report_data,
        'report_account': report_account,
    }
    return render(request, 'accounting_dashboard.html', context)

@require_dashboard('services_dashboard')
def services_dashboard(request):
    return render(
        request,
        'services_dashboard.html',
        {
            'modules': MANAGEMENT_MODULES,
            'repair_reports': ServiceRepairReport.objects.all()[:8],
            'job_orders': JobOrder.objects.all()[:8],
            'material_borrows': MaterialBorrow.objects.prefetch_related('lines').all()[:8],
            'official_business_forms': OfficialBusinessForm.objects.all()[:8],
            'inventory_items': InventoryItem.objects.order_by('name'),
            'repair_report_count': ServiceRepairReport.objects.count(),
            'job_order_count': JobOrder.objects.count(),
            'material_borrow_count': MaterialBorrow.objects.count(),
            'official_business_count': OfficialBusinessForm.objects.count(),
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
    required = ('job_order_number', 'date_filed', 'job_description')
    if not all(request.POST.get(field, '').strip() for field in required):
        messages.error(request, 'Please complete all required Job Order fields.')
        return redirect(f"{reverse('services_dashboard')}?tab=jobOrderTab")
    names = '\n'.join(
        name.strip()
        for name in request.POST.getlist('assignee_names')
        if name.strip()
    )
    dates_covered = '\n'.join(
        date_value.strip()
        for date_value in request.POST.getlist('dates_covered')
        if date_value.strip()
    )
    try:
        JobOrder.objects.create(
            job_order_number=request.POST['job_order_number'].strip(),
            names=names,
            date_filed=request.POST['date_filed'],
            dates_covered=dates_covered,
            area_assignment=request.POST.get('area_assignment', '').strip(),
            job_description=request.POST['job_description'].strip(),
            prepared_by=request.POST.get('prepared_by', '').strip(),
            noted_by=request.POST.get('noted_by', '').strip(),
            approved_by=request.POST.get('approved_by', '').strip(),
        )
        messages.success(request, 'Job Order saved successfully.')
    except Exception as exc:
        messages.error(request, f'Could not save job order: {exc}')
    return redirect(f"{reverse('services_dashboard')}?tab=jobOrderTab")


@login_required
@require_POST
def create_material_borrow(request):
    required = ('borrow_number', 'date_borrowed', 'borrower_name')
    if not all(request.POST.get(field, '').strip() for field in required):
        messages.error(request, 'Please complete all required Borrow Material fields.')
        return redirect(f"{reverse('services_dashboard')}?tab=borrowMaterialTab")

    descriptions = request.POST.getlist('borrow_item_description')
    quantities = request.POST.getlist('borrow_item_quantity')
    units = request.POST.getlist('borrow_item_unit')
    remarks_list = request.POST.getlist('borrow_item_remarks')
    inventory_ids = request.POST.getlist('borrow_item_inventory')

    lines = []
    for index, description in enumerate(descriptions):
        description = description.strip()
        if not description:
            continue
        try:
            quantity = int(quantities[index]) if index < len(quantities) and quantities[index] else 1
        except (TypeError, ValueError):
            quantity = 1
        quantity = max(quantity, 1)
        unit = units[index].strip() if index < len(units) else 'pcs'
        remark = remarks_list[index].strip() if index < len(remarks_list) else ''
        inventory_id = inventory_ids[index].strip() if index < len(inventory_ids) else ''
        inventory_item = None
        if inventory_id.isdigit():
            inventory_item = InventoryItem.objects.filter(pk=int(inventory_id)).first()
        lines.append({
            'inventory_item': inventory_item,
            'item_description': description,
            'quantity': quantity,
            'unit': unit or 'pcs',
            'remarks': remark,
        })

    if not lines:
        messages.error(request, 'Please add at least one item to borrow.')
        return redirect(f"{reverse('services_dashboard')}?tab=borrowMaterialTab")

    expected_return_date = request.POST.get('expected_return_date', '').strip() or None
    try:
        borrow = MaterialBorrow.objects.create(
            borrow_number=request.POST['borrow_number'].strip(),
            date_borrowed=request.POST['date_borrowed'],
            borrower_name=request.POST['borrower_name'].strip(),
            department=request.POST.get('department', '').strip(),
            purpose=request.POST.get('purpose', '').strip(),
            expected_return_date=expected_return_date,
            remarks=request.POST.get('remarks', '').strip(),
            prepared_by=request.POST.get('prepared_by', '').strip(),
            noted_by=request.POST.get('noted_by', '').strip(),
            approved_by=request.POST.get('approved_by', '').strip(),
        )
        MaterialBorrowLine.objects.bulk_create([
            MaterialBorrowLine(material_borrow=borrow, **line)
            for line in lines
        ])
        messages.success(request, 'Borrow material slip saved successfully.')
    except Exception as exc:
        messages.error(request, f'Could not save borrow material slip: {exc}')
    return redirect(f"{reverse('services_dashboard')}?tab=borrowMaterialTab")


@login_required
@require_POST
def create_official_business_form(request):
    required = ('name', 'application_date')
    if not all(request.POST.get(field, '').strip() for field in required):
        messages.error(request, 'Please complete all required Official Business Form fields.')
        return redirect(f"{reverse('services_dashboard')}?tab=officialBusinessTab")

    ob_dates = '\n'.join(
        date_value.strip()
        for date_value in request.POST.getlist('ob_dates')
        if date_value.strip()
    )
    time_departure = request.POST.get('time_departure', '').strip() or None
    time_return = request.POST.get('time_return', '').strip() or None
    try:
        OfficialBusinessForm.objects.create(
            name=request.POST['name'].strip(),
            designation=request.POST.get('designation', '').strip(),
            application_date=request.POST['application_date'],
            ob_dates=ob_dates,
            destination=request.POST.get('destination', '').strip(),
            time_departure=time_departure,
            time_return=time_return,
            purpose=request.POST.get('purpose', '').strip(),
            prepared_by=request.POST.get('prepared_by', '').strip(),
        )
        messages.success(request, 'Official Business Form saved successfully.')
    except Exception as exc:
        messages.error(request, f'Could not save Official Business Form: {exc}')
    return redirect(f"{reverse('services_dashboard')}?tab=officialBusinessTab")


@login_required
@require_POST
def approve_official_business_form(request, ob_id):
    ob_form = get_object_or_404(OfficialBusinessForm, pk=ob_id)
    ob_form.status = 'approved'
    ob_form.approved_at = timezone.now()
    ob_form.save(update_fields=['status', 'approved_at'])
    messages.success(request, f'Official Business Form for {ob_form.name} approved.')
    return redirect(f"{reverse('services_dashboard')}?tab=officialBusinessTab")


@login_required
@require_POST
def reject_official_business_form(request, ob_id):
    ob_form = get_object_or_404(OfficialBusinessForm, pk=ob_id)
    ob_form.status = 'rejected'
    ob_form.approved_at = timezone.now()
    ob_form.save(update_fields=['status', 'approved_at'])
    messages.success(request, f'Official Business Form for {ob_form.name} rejected.')
    return redirect(f"{reverse('services_dashboard')}?tab=officialBusinessTab")


SERVICE_FIELD_LABELS = {
    'repair': [('Report No.', 'report_number'), ('Report Date', 'report_date'), ('Customer / Company', 'customer_name'),
               ('Contact Person', 'contact_person'), ('Contact Number', 'contact_number'), ('Customer Address', 'customer_address'),
               ('Equipment / Unit', 'equipment'), ('Model No.', 'model_number'), ('Serial No.', 'serial_number'),
               ('Reported Complaint / Issue', 'complaint'), ('Diagnosis', 'diagnosis'), ('Repairs Performed', 'repairs_performed'),
               ('Parts / Materials Used', 'parts_used'), ('Technician', 'technician'), ('Status', 'get_status_display'),
               ('Recommendations', 'recommendations')],
    'job': [
        ('Job Order No.', 'job_order_number'),
        ('Name/s', 'names_display'),
        ('Date Filed', 'date_filed'),
        ('Date/s Covered', 'dates_covered_display'),
        ('Area Assignment', 'area_assignment'),
        ('Job Description', 'job_description'),
        ('Prepared by', 'prepared_by'),
        ('Noted by', 'noted_by'),
        ('Approved by', 'approved_by'),
    ],
    'borrow': [
        ('Borrow No.', 'borrow_number'),
        ('Date Borrowed', 'date_borrowed'),
        ('Borrower', 'borrower_name'),
        ('Department', 'department'),
        ('Purpose', 'purpose'),
        ('Expected Return', 'expected_return_date'),
        ('Remarks', 'remarks'),
        ('Prepared by', 'prepared_by'),
        ('Noted by', 'noted_by'),
        ('Approved by', 'approved_by'),
        ('Status', 'get_status_display'),
    ],
    'ob': [
        ('Name', 'name'),
        ('Designation', 'designation'),
        ('Application Date', 'application_date'),
        ('OB Date/s', 'ob_dates_display'),
        ('OB Address / Destination', 'destination'),
        ('Time of Departure', 'time_departure'),
        ('Time of Return', 'time_return'),
        ('Purpose/s', 'purpose'),
        ('Prepared by (Employee)', 'prepared_by'),
        ('Approved by', 'approved_by_display'),
        ('Status', 'get_status_display'),
    ],
}


def _service_record_context(record, document_type):
    fields = []
    for label, attribute in SERVICE_FIELD_LABELS[document_type]:
        value = getattr(record, attribute)
        value = value() if callable(value) else value
        if hasattr(value, 'strftime'):
            value = value.strftime('%B %d, %Y')
        fields.append((label, value or '—'))
    return {'record': record, 'fields': fields, 'document_type': document_type}


def _borrow_record_context(record):
    context = _service_record_context(record, 'borrow')
    context['borrow_lines'] = record.lines.all()
    return context


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


@login_required
def view_official_business_form(request, ob_id):
    return render(request, 'service_document_detail.html', _service_record_context(
        get_object_or_404(OfficialBusinessForm, pk=ob_id), 'ob'))


@login_required
def edit_official_business_form(request, ob_id):
    ob_form = get_object_or_404(OfficialBusinessForm, pk=ob_id)
    form = OfficialBusinessFormForm(request.POST or None, instance=ob_form)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Official Business Form updated successfully.')
        return redirect('view_official_business_form', ob_id=ob_form.id)
    return render(request, 'service_document_form.html', {'form': form, 'record': ob_form, 'document_type': 'ob'})


@login_required
@require_POST
def delete_official_business_form(request, ob_id):
    get_object_or_404(OfficialBusinessForm, pk=ob_id).delete()
    messages.success(request, 'Official Business Form deleted.')
    return redirect(f"{reverse('services_dashboard')}?tab=officialBusinessTab")


@login_required
def view_material_borrow(request, borrow_id):
    return render(request, 'service_document_detail.html', _borrow_record_context(
        get_object_or_404(MaterialBorrow.objects.prefetch_related('lines'), pk=borrow_id)))


@login_required
def edit_material_borrow(request, borrow_id):
    borrow = get_object_or_404(MaterialBorrow, pk=borrow_id)
    form = MaterialBorrowForm(request.POST or None, instance=borrow)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Borrow material slip updated successfully.')
        return redirect('view_material_borrow', borrow_id=borrow.id)
    return render(request, 'service_document_form.html', {
        'form': form,
        'record': borrow,
        'document_type': 'borrow',
    })


@login_required
@require_POST
def delete_material_borrow(request, borrow_id):
    get_object_or_404(MaterialBorrow, pk=borrow_id).delete()
    messages.success(request, 'Borrow material slip deleted.')
    return redirect(f"{reverse('services_dashboard')}?tab=borrowMaterialTab")


@login_required
@require_POST
def return_material_borrow(request, borrow_id):
    borrow = get_object_or_404(MaterialBorrow, pk=borrow_id)
    if borrow.status == 'returned':
        messages.info(request, f'Borrow slip {borrow.borrow_number} is already marked as returned.')
    else:
        borrow.status = 'returned'
        borrow.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Borrow slip {borrow.borrow_number} marked as returned.')
    return redirect(f"{reverse('services_dashboard')}?tab=borrowMaterialTab")
