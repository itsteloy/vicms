from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from .models import InventoryItem, InventoryCategory, SalesOrder, HRDocument, Employee, Company, Position, PayPeriod, PayrollRun, PayrollLine, DeductionConfig, EmployeeDeduction,TaxBracket, AttendanceLog, AttendanceSheet, AttendanceSheetEntry, AttendanceSheetPunch, ShiftSchedule, LeaveBalance, LeaveRequest, Holiday, RefundRecord, Delivery, DeliveryLine, Quotation, QuotationLine, ServiceQuotation, ServiceQuotationLine, SalesDocumentArchive, ServiceRepairReport, JobOrder, JobOrderIdlePeriod, estimated_daily_rate, idle_calendar_days, MaterialBorrow, MaterialBorrowLine, OfficialBusinessForm, DeliveryReceipt, DeliveryReceiptLine, TravelOrderForm, WorkspaceAccount, Account, JournalEntry, JournalEntryLine, BankAccount, BankTransaction, Customer, Invoice, InvoicePayment, Supplier, Bill, BillPayment, PayrollExpenseEntry, TaxDeadline, WaterZone, WaterCustomer, WaterMeterReading, WaterBill, WaterPayment, WaterServiceAction, WaterServiceContract, WaterAuditLog, WATER_CUSTOMER_TYPES, WATER_CONNECTION_STATUS, WATER_PAYMENT_METHODS, WATER_BILL_STATUS, WATER_SERVICE_ACTION_TYPES, WATER_SERVICE_ACTION_STATUS, WATER_CONTRACT_APPLICATION_STATUS, WATER_CONTRACT_HOME_OWNERSHIP, WATER_CONTRACT_CLASSIFICATION, WATER_CONTRACT_CIVIL_STATUS
from . import accounting_engine
from . import accounting_reports
from .attendance_sheet_parser import AttendanceSheetParseError, parse_attendance_sheet_file
from .attendance_sheet_metrics import annotate_attendance_sheet
from .inventory_product_code import generate_inventory_product_code, next_product_codes_by_category
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
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
from .forms import EmployeeForm, JobOrderForm, JobOrderIdlePeriodForm, MaterialBorrowForm, OfficialBusinessFormForm, DeliveryReceiptForm, TravelOrderFormForm, ServiceRepairReportForm
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Sum, Count, Q, OuterRef, Subquery, F, Value, DecimalField, Min, ExpressionWrapper
from django.db.models.functions import Coalesce, Greatest
import traceback
import json
import csv

MANAGEMENT_MODULES = [
    {
        'name': 'HR',
        'summary': 'Employee records, attendance, payroll, staff requests, and document status.',
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
        'name': 'Accounting',
        'summary': 'Salary records, deductions, approvals, and pay schedules.',
        'status': 'Active',
        'url_name': 'accounting_dashboard',
        'workspace_key': 'accounting',
    },
    {
        'name': 'Services',
        'summary': 'Repair reports, borrow slips, job orders, travel orders, and official business forms.',
        'status': 'Active',
        'url_name': 'services_dashboard',
        'workspace_key': 'services',
    },
    {
        'name': 'Water Billing',
        'summary': 'Customer accounts, meter readings, billing, payments, collections, and disconnections.',
        'status': 'Active',
        'url_name': 'water_billing_dashboard',
        'workspace_key': 'water_billing',
    },
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


def _inventory_category_path(category, cache=None):
    """Build 'Parent › Child › Leaf' label for a category."""
    if category is None:
        return ''
    if cache is not None and category.pk in cache:
        return cache[category.pk]
    parts = []
    node = category
    seen = set()
    while node is not None and node.pk not in seen:
        seen.add(node.pk)
        parts.append(node.name)
        node = node.parent
    label = ' › '.join(reversed(parts))
    if cache is not None:
        cache[category.pk] = label
    return label


def inventory_category_choices():
    """Flattened nested categories for selects, indented by depth."""
    categories = list(
        InventoryCategory.objects.select_related('parent').order_by('name', 'id')
    )
    children_map = defaultdict(list)
    for category in categories:
        parent_id = category.parent_id
        children_map[parent_id].append(category)

    for siblings in children_map.values():
        siblings.sort(key=lambda c: (c.name.lower(), c.id))

    path_cache = {}
    choices = []

    def walk(parent_id, depth, root_name=None, root_id=None):
        for category in children_map.get(parent_id, []):
            label = _inventory_category_path(category, path_cache)
            current_root_name = root_name if root_name else category.name
            current_root_id = root_id if root_id else category.id
            choices.append({
                'id': category.id,
                'name': category.name,
                'path': label,
                'depth': depth,
                'display': category.name,
                'parent_id': category.parent_id,
                'root_id': current_root_id,
                'root_name': current_root_name,
            })
            walk(category.id, depth + 1, current_root_name, current_root_id)

    walk(None, 0)
    return choices


def inventory_category_tree():
    """Nested category tree for cascading menu UI."""
    categories = list(
        InventoryCategory.objects.select_related('parent').order_by('name', 'id')
    )
    children_map = defaultdict(list)
    for category in categories:
        children_map[category.parent_id].append(category)

    for siblings in children_map.values():
        siblings.sort(key=lambda c: (c.name.lower(), c.id))

    path_cache = {}

    def build_node(category):
        return {
            'id': category.id,
            'name': category.name,
            'path': _inventory_category_path(category, path_cache),
            'children': [build_node(child) for child in children_map.get(category.id, [])],
        }

    return [build_node(category) for category in children_map.get(None, [])]


def inventory_category_groups():
    """Group flat category choices under their root for dropdown UI."""
    groups = []
    index = {}
    for choice in inventory_category_choices():
        root_id = choice['root_id']
        if root_id not in index:
            group = {'root_id': root_id, 'name': choice['root_name'], 'items': []}
            index[root_id] = group
            groups.append(group)
        index[root_id]['items'].append(choice)
    groups.sort(key=lambda g: g['name'].lower())
    return groups


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
    if workspace.dashboard_url_name == url_name:
        return True
    # Payroll was merged into HR â€” keep legacy payroll workspace accounts working.
    if url_name == 'hr_dashboard' and workspace.dashboard_url_name == 'payroll_dashboard':
        return True
    return False


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


DOCUMENT_HR_TABS = {
    'job': 'jobOrderTab',
    'ob': 'officialBusinessTab',
    'travel': 'travelOrderTab',
}

DOCUMENT_SERVICES_TABS = {
    **DOCUMENT_HR_TABS,
    'repair': 'repairTab',
    'borrow': 'borrowMaterialTab',
}


def _document_back_link(request, document_type):
    from_source = request.GET.get('from', '').strip()
    if from_source == 'hr' and document_type in DOCUMENT_HR_TABS:
        return (
            f"{reverse('hr_dashboard')}?tab={DOCUMENT_HR_TABS[document_type]}",
            'HR Dashboard',
        )
    if from_source == 'services' and document_type in DOCUMENT_SERVICES_TABS:
        return (
            f"{reverse('services_dashboard')}?tab={DOCUMENT_SERVICES_TABS[document_type]}",
            'Services Dashboard',
        )
    if from_source == 'sales' and document_type == 'delivery_receipt':
        return (
            f"{reverse('sales_dashboard')}?tab=delivery-receipt-tab",
            'Sales Dashboard',
        )

    workspace = get_user_workspace(request.user)
    if workspace:
        if workspace.dashboard_url_name == 'hr_dashboard' and document_type in DOCUMENT_HR_TABS:
            return (
                f"{reverse('hr_dashboard')}?tab={DOCUMENT_HR_TABS[document_type]}",
                'HR Dashboard',
            )
        if workspace.dashboard_url_name == 'services_dashboard' and document_type in DOCUMENT_SERVICES_TABS:
            return (
                f"{reverse('services_dashboard')}?tab={DOCUMENT_SERVICES_TABS[document_type]}",
                'Services Dashboard',
            )
        if workspace.dashboard_url_name == 'sales_dashboard' and document_type == 'delivery_receipt':
            return (
                f"{reverse('sales_dashboard')}?tab=delivery-receipt-tab",
                'Sales Dashboard',
            )

    if user_has_dashboard_access(request.user, 'services_dashboard') and document_type in DOCUMENT_SERVICES_TABS:
        return (
            f"{reverse('services_dashboard')}?tab={DOCUMENT_SERVICES_TABS[document_type]}",
            'Services Dashboard',
        )
    if user_has_dashboard_access(request.user, 'hr_dashboard') and document_type in DOCUMENT_HR_TABS:
        return (
            f"{reverse('hr_dashboard')}?tab={DOCUMENT_HR_TABS[document_type]}",
            'HR Dashboard',
        )
    if document_type == 'delivery_receipt' and user_has_dashboard_access(request.user, 'sales_dashboard'):
        return (
            f"{reverse('sales_dashboard')}?tab=delivery-receipt-tab",
            'Sales Dashboard',
        )
    return reverse('dashboard'), 'Dashboard'


def _enrich_document_context(request, context, document_type):
    back_url, back_label = _document_back_link(request, document_type)
    context['back_url'] = back_url
    context['back_label'] = back_label
    context['can_manage_services'] = user_has_dashboard_access(request.user, 'services_dashboard')
    return context


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
        if action in PAYROLL_POST_ACTIONS:
            return _process_payroll_post(request)

        if action == 'create_company':
            name = request.POST.get('company_name', '').strip()
            if not name:
                messages.error(request, 'Company name is required.')
            elif Company.objects.filter(name__iexact=name).exists():
                messages.warning(request, f'Company "{name}" already exists.')
            else:
                Company.objects.create(name=name)
                messages.success(request, f'Company "{name}" created.')
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
            return redirect(f"{reverse('hr_dashboard')}?tab=attendanceSheetsTab")

        # Remove an incorrect attendance log
        if action == 'delete_attendance':
            att_id = request.POST.get('attendance_id', '').strip()
            if att_id:
                AttendanceLog.objects.filter(pk=att_id).delete()
                messages.success(request, 'Attendance record removed.')
            return redirect(f"{reverse('hr_dashboard')}?tab=attendanceSheetsTab")

        # Upload biometric punch sheet (.xls) and generate editable layout
        if action == 'upload_punch_sheet':
            uploaded = request.FILES.get('punch_sheet_file')
            if not uploaded:
                messages.error(request, 'Please choose an attendance sheet (.xls) file to upload.')
                return redirect(f"{reverse('hr_dashboard')}?tab=attendanceSheetsTab")

            filename = (uploaded.name or '').lower()
            if not (filename.endswith('.xls') or filename.endswith('.xml')):
                messages.error(request, 'Only .xls attendance sheet exports are supported.')
                return redirect(f"{reverse('hr_dashboard')}?tab=attendanceSheetsTab")

            try:
                parsed = parse_attendance_sheet_file(uploaded)
            except AttendanceSheetParseError as exc:
                messages.error(request, str(exc))
                return redirect(f"{reverse('hr_dashboard')}?tab=attendanceSheetsTab")

            with transaction.atomic():
                sheet = AttendanceSheet.objects.create(
                    title=parsed['title'],
                    period_year=parsed.get('period_year'),
                    period_start=parsed.get('period_start'),
                    period_end=parsed.get('period_end'),
                    source_file=uploaded,
                    original_filename=uploaded.name or '',
                )
                for emp_idx, emp in enumerate(parsed['employees']):
                    entry = AttendanceSheetEntry.objects.create(
                        sheet=sheet,
                        device_employee_id=emp.get('device_employee_id', ''),
                        employee_name=emp.get('employee_name', ''),
                        department=emp.get('department', ''),
                        shift=emp.get('shift', ''),
                        sort_order=emp_idx,
                    )
                    AttendanceSheetPunch.objects.bulk_create([
                        AttendanceSheetPunch(
                            entry=entry,
                            day=int(punch['day']),
                            punch_date=punch.get('punch_date'),
                            punch_times=punch.get('punch_times', '') or '',
                            morning_in=punch.get('morning_in', '') or '',
                            morning_out=punch.get('morning_out', '') or '',
                            afternoon_in=punch.get('afternoon_in', '') or '',
                            afternoon_out=punch.get('afternoon_out', '') or '',
                            sort_order=punch.get('sort_order', idx),
                        )
                        for idx, punch in enumerate(emp.get('punches') or [])
                    ])

                from .employee_name_match import link_attendance_entries
                link_result = link_attendance_entries(
                    list(sheet.entries.all()),
                    clear_existing=False,
                )

            messages.success(
                request,
                f'Attendance sheet imported with {len(parsed["employees"])} row(s); '
                f'{link_result["linked"]} linked to EMP IDs. You can edit the layout below.',
            )
            return redirect(f"{reverse('hr_dashboard')}?tab=attendanceSheetsTab&sheet={sheet.id}")

        # Save edits to an imported punch sheet layout
        if action == 'save_punch_sheet':
            sheet_id = request.POST.get('sheet_id', '').strip()
            sheet = AttendanceSheet.objects.filter(pk=sheet_id).first()
            if not sheet:
                messages.error(request, 'Punch sheet not found.')
                return redirect(f"{reverse('hr_dashboard')}?tab=attendanceSheetsTab")

            title = request.POST.get('sheet_title', '').strip() or sheet.title
            with transaction.atomic():
                sheet.title = title
                sheet.save(update_fields=['title', 'updated_at'])

                for entry in sheet.entries.all():
                    prefix = f'entry_{entry.id}_'
                    entry.device_employee_id = request.POST.get(f'{prefix}device_id', entry.device_employee_id).strip()
                    entry.employee_name = request.POST.get(f'{prefix}name', entry.employee_name).strip()
                    entry.department = request.POST.get(f'{prefix}department', entry.department).strip()
                    entry.shift = request.POST.get(f'{prefix}shift', entry.shift).strip()
                    entry.save(update_fields=['device_employee_id', 'employee_name', 'department', 'shift'])

                    for punch in entry.punches.all():
                        punch.morning_in = request.POST.get(f'punch_{punch.id}_morning_in', punch.morning_in).strip()
                        punch.morning_out = request.POST.get(f'punch_{punch.id}_morning_out', punch.morning_out).strip()
                        punch.afternoon_in = request.POST.get(f'punch_{punch.id}_afternoon_in', punch.afternoon_in).strip()
                        punch.afternoon_out = request.POST.get(f'punch_{punch.id}_afternoon_out', punch.afternoon_out).strip()
                        punch.sync_to_punch_times()
                        punch.save(update_fields=[
                            'morning_in', 'morning_out', 'afternoon_in', 'afternoon_out', 'punch_times',
                        ])

                from .employee_name_match import link_attendance_entries
                link_attendance_entries(list(sheet.entries.all()), clear_existing=True)

            messages.success(request, 'Attendance sheet saved and EMP links refreshed.')
            return redirect(f"{reverse('hr_dashboard')}?tab=attendanceSheetsTab&sheet={sheet.id}")

        # Delete an imported punch sheet
        if action == 'delete_punch_sheet':
            sheet_id = request.POST.get('sheet_id', '').strip()
            sheet = AttendanceSheet.objects.filter(pk=sheet_id).first()
            if sheet:
                sheet.delete()
                messages.success(request, 'Punch sheet deleted.')
            else:
                messages.error(request, 'Punch sheet not found.')
            return redirect(f"{reverse('hr_dashboard')}?tab=attendanceSheetsTab")

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

    employees = Employee.objects.select_related('company', 'position').order_by('last_name', 'first_name')
    active_employee_count = employees.filter(termination_date__isnull=True).count()
    documents = HRDocument.objects.all()

    # â”€â”€ Attendance tab: optional filters (employee / date range), defaults to last 14 days â”€â”€
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

    # ── Punch sheets tab ──
    punch_sheets = AttendanceSheet.objects.annotate(
        entry_count=Count('entries'),
    ).order_by('-uploaded_at')[:50]
    selected_punch_sheet = None
    punch_sheet_id = request.GET.get('sheet', '').strip()
    if punch_sheet_id:
        selected_punch_sheet = (
            AttendanceSheet.objects.prefetch_related(
                'entries__punches',
                'entries__linked_employee__company',
            )
            .filter(pk=punch_sheet_id)
            .first()
        )
        selected_punch_sheet = annotate_attendance_sheet(selected_punch_sheet)

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
            'companies': Company.objects.order_by('name'),
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
            'punch_sheets': punch_sheets,
            'selected_punch_sheet': selected_punch_sheet,
            'leave_requests': leave_requests,
            'leave_type_choices': LeaveBalance.LEAVE_TYPES,
            'pending_leave_count': pending_leave_count,
            'job_orders': JobOrder.objects.prefetch_related('assignees', 'idle_periods').all()[:8],
            'job_order_count': JobOrder.objects.count(),
            'official_business_forms': OfficialBusinessForm.objects.all()[:8],
            'official_business_count': OfficialBusinessForm.objects.count(),
            'travel_order_forms': TravelOrderForm.objects.all()[:8],
            'travel_order_count': TravelOrderForm.objects.count(),
            'can_access_services': user_has_dashboard_access(request.user, 'services_dashboard'),
            **_build_idle_days_report(request),
            **_payroll_dashboard_context(),
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
    tab_param = (request.GET.get('tab') or '').strip()
    valid_sales_tabs = {
        'sales-tab', 'history-tab', 'refund-tab', 'analytics-tab',
        'product-quotation-tab', 'service-quotation-tab', 'collection-form-tab',
        'ageing-accounts-tab', 'retention-summary-tab', 'petty-cash-tab',
        'saved-documents-tab', 'delivery-receipt-tab',
    }
    if tab_param in valid_sales_tabs:
        active_tab = tab_param
    elif any([start_date, end_date, customer, item_name, refund_status]):
        active_tab = 'history-tab'

    recent_quotations = Quotation.objects.all()[:10]
    recent_service_quotations = ServiceQuotation.objects.all()[:10]

    doc_type_filter = (request.GET.get('doc_type') or 'all').strip()
    saved_documents_qs = SalesDocumentArchive.objects.select_related('created_by').all()
    if doc_type_filter and doc_type_filter != 'all':
        saved_documents_qs = saved_documents_qs.filter(document_type=doc_type_filter)
    saved_docs_paginator = Paginator(saved_documents_qs, 20)
    try:
        saved_docs_page = int(request.GET.get('docs_page') or 1)
    except (TypeError, ValueError):
        saved_docs_page = 1
    saved_documents_page = saved_docs_paginator.get_page(saved_docs_page)

    return render(
        request,
        'sales_dashboard.html',
        {
            'inventory_items': inventory_items,
            'recent_quotations': recent_quotations,
            'recent_service_quotations': recent_service_quotations,
            'next_product_quotation_number': Quotation.generate_quotation_number(),
            'next_service_quotation_number': ServiceQuotation.generate_quotation_number(),
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
            'saved_documents_page': saved_documents_page,
            'saved_document_types': SalesDocumentArchive.DOCUMENT_TYPES,
            'saved_doc_type_filter': doc_type_filter,
            'delivery_receipts': DeliveryReceipt.objects.prefetch_related('lines').all()[:8],
            'delivery_receipt_count': DeliveryReceipt.objects.count(),
            'next_receipt_number': DeliveryReceipt.generate_receipt_number(),
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
            quotation_number=payload.get("quotation_number", "").strip() or Quotation.generate_quotation_number(),
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
        return JsonResponse({
            "id": quotation.id,
            "download_url": download_url,
            "quotation_number": quotation.quotation_number,
            "next_quotation_number": Quotation.generate_quotation_number(),
        })

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
            quotation_number=payload.get("quotation_number", "").strip() or ServiceQuotation.generate_quotation_number(),
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
        return JsonResponse({
            "id": quotation.id,
            "download_url": download_url,
            "quotation_number": quotation.quotation_number,
            "next_quotation_number": ServiceQuotation.generate_quotation_number(),
        })

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


@login_required
@require_POST
def save_sales_document_pdf(request):
    """Accept a generated PDF from Sales dashboard forms and store it."""
    pdf_file = request.FILES.get('pdf')
    if not pdf_file:
        return JsonResponse({'error': 'PDF file is required.'}, status=400)

    content_type = (getattr(pdf_file, 'content_type', '') or '').lower()
    name = (getattr(pdf_file, 'name', '') or '').lower()
    if 'pdf' not in content_type and not name.endswith('.pdf'):
        return JsonResponse({'error': 'Uploaded file must be a PDF.'}, status=400)

    document_type = (request.POST.get('document_type') or '').strip()
    valid_types = {choice[0] for choice in SalesDocumentArchive.DOCUMENT_TYPES}
    if document_type not in valid_types:
        return JsonResponse({'error': 'Invalid document type.'}, status=400)

    title = (request.POST.get('title') or '').strip() or document_type.replace('_', ' ').title()
    reference = (request.POST.get('reference') or '').strip()
    source_id_raw = (request.POST.get('source_id') or '').strip()
    source_id = None
    if source_id_raw:
        try:
            source_id = int(source_id_raw)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid source_id.'}, status=400)

    try:
        archive = SalesDocumentArchive.objects.create(
            document_type=document_type,
            title=title[:255],
            reference=reference[:120],
            source_id=source_id,
            pdf=pdf_file,
            created_by=request.user if request.user.is_authenticated else None,
        )
    except Exception as e:
        logger.exception('save_sales_document_pdf error')
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({
        'id': archive.id,
        'title': archive.title,
        'document_type': archive.document_type,
        'reference': archive.reference,
        'created_at': archive.created_at.isoformat(),
        'pdf_url': archive.pdf.url if archive.pdf else '',
    })


def _sales_document_pdf_response(archive, inline=False):
    if not archive.pdf:
        return HttpResponse('PDF file not found.', status=404)
    try:
        archive.pdf.open('rb')
        pdf_bytes = archive.pdf.read()
    finally:
        try:
            archive.pdf.close()
        except Exception:
            pass

    safe_name = ''.join(
        ch if ch.isalnum() or ch in '-_.' else '_'
        for ch in (archive.reference or archive.title or f'sales_document_{archive.pk}')
    )
    if not safe_name.lower().endswith('.pdf'):
        safe_name = f'{safe_name}.pdf'

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    disposition = 'inline' if inline else 'attachment'
    response['Content-Disposition'] = f'{disposition}; filename="{safe_name}"'
    return response


@login_required
def view_sales_document_pdf(request, document_id):
    archive = get_object_or_404(SalesDocumentArchive, pk=document_id)
    return _sales_document_pdf_response(archive, inline=True)


@login_required
def download_sales_document_pdf(request, document_id):
    archive = get_object_or_404(SalesDocumentArchive, pk=document_id)
    return _sales_document_pdf_response(archive, inline=False)


@require_dashboard('inventory_dashboard')
def inventory_dashboard(request):
    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
        item_id = request.POST.get('itemId', '').strip()
        name = request.POST.get('itemName', '').strip()

        if action == 'create_category':
            category_name = request.POST.get('category_name', '').strip()
            parent_id = request.POST.get('category_parent', '').strip()
            if not category_name:
                messages.error(request, 'Category name is required.')
                return redirect(f"{reverse('inventory_dashboard')}?tab=managePanel")

            parent = None
            if parent_id:
                parent = InventoryCategory.objects.filter(pk=parent_id).first()
                if parent is None:
                    messages.error(request, 'Selected parent category was not found.')
                    return redirect(f"{reverse('inventory_dashboard')}?tab=managePanel")

            exists = InventoryCategory.objects.filter(
                name__iexact=category_name,
                parent=parent,
            ).exists()
            if exists:
                label = parent.path_label if parent else 'top level'
                messages.error(request, f'“{category_name}” already exists under {label}.')
                return redirect(f"{reverse('inventory_dashboard')}?tab=managePanel")

            category = InventoryCategory.objects.create(name=category_name, parent=parent)
            messages.success(
                request,
                f'Category “{category.path_label}” created. It is now available in the item dropdown.',
            )
            return redirect(f"{reverse('inventory_dashboard')}?tab=managePanel")

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

        category_id = request.POST.get('categoryId', '').strip()
        category = None
        if category_id:
            category = InventoryCategory.objects.filter(pk=category_id).first()
            if category is None:
                messages.error(request, 'Selected category was not found.')
                return redirect('inventory_dashboard')
            name = category.path_label

        if name:
            if item_id:
                item = InventoryItem.objects.get(pk=item_id)
                previous_category_id = item.category_id
            else:
                item = InventoryItem()
                previous_category_id = None

            item.name = name
            item.category = category
            if category and (not item_id or previous_category_id != category.id):
                item.product_code = generate_inventory_product_code(
                    category,
                    exclude_item_id=item.pk,
                )
            elif not item.product_code and category:
                item.product_code = generate_inventory_product_code(
                    category,
                    exclude_item_id=item.pk,
                )
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
            item.notes = request.POST.get('notes', '').strip()
            item.save()
            messages.success(request, 'Inventory item saved.')

        return redirect('inventory_dashboard')

    inventory_items = InventoryItem.objects.select_related('category').all().order_by('-created_at')
    category_choices = inventory_category_choices()
    category_groups = inventory_category_groups()
    category_tree = inventory_category_tree()
    next_product_codes = next_product_codes_by_category()
    path_by_id = {c['id']: c['path'] for c in category_choices}
    inventory_items_json = [
        {
            'id': item.id,
            'productCode': item.product_code,
            'name': item.name,
            'categoryId': item.category_id,
            'categoryPath': path_by_id.get(item.category_id, item.name),
            'picture': item.picture.url if getattr(item, 'picture') else '',
            'size': item.size,
            'stockAvailable': item.stock_available,
            'pcsPerCtn': item.pcs_per_ctn,
            'cartonSize': item.carton_size,
            'netWeight': float(item.net_weight),
            'grossWeight': float(item.gross_weight),
            'price': float(item.price),
            'description': item.description,
            'notes': item.notes,
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
            'inventory_categories': category_choices,
            'inventory_category_groups': category_groups,
            'inventory_category_tree': category_tree,
            'next_product_codes': next_product_codes,
            'deliveries': deliveries,
            'total_stock': sum(item.stock_available for item in inventory_items),
            'low_stock_count': sum(1 for item in inventory_items if item.stock_available < 10),
            'modules': MANAGEMENT_MODULES,
        },
    )


PAYROLL_POST_ACTIONS = frozenset({
    'create_pay_period',
    'create_payrun',
    'compute_payroll',
    'save_payroll_overtime',
    'approve_payroll',
    'disburse_payroll',
    'add_deduction',
    'assign_deduction',
    'delete_run',
    'close_period',
})


def _process_payroll_post(request):
    action = request.POST.get('action', '').strip()

    # ---------- CREATE PAY PERIOD ----------
    if action == 'create_pay_period':
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        pay_date = request.POST.get('pay_date', '').strip()
        period_type = request.POST.get('period_type', 'semi-monthly').strip()

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
                        period_type=period_type if period_type in ('monthly', 'semi-monthly') else 'semi-monthly',
                    )
                    messages.success(
                        request,
                        f'Pay period {period.start_date} â€“ {period.end_date} created. You can now create a pay run.',
                    )
            except ValueError:
                messages.error(request, 'Invalid date format.')
            except Exception as exc:
                messages.error(request, f'Could not create pay period: {exc}')
        return redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")

    # ---------- CREATE PAY RUN ----------
    if action == 'create_payrun':
        pay_period_id = request.POST.get('pay_period_id')
        use_attendance_sheets = request.POST.get('use_attendance_sheets') == 'on'
        align_cutoff_to_sheets = request.POST.get('align_cutoff_to_sheets') == 'on'
        raw_sheet_ids = request.POST.getlist('attendance_sheet_ids')
        selected_sheet_ids = []
        for raw in raw_sheet_ids:
            try:
                selected_sheet_ids.append(int(raw))
            except (TypeError, ValueError):
                continue
        # Keep only sheets that exist
        if selected_sheet_ids:
            selected_sheet_ids = list(
                AttendanceSheet.objects.filter(id__in=selected_sheet_ids)
                .order_by('-uploaded_at', '-id')
                .values_list('id', flat=True)
            )

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
                        cutoff_start = pay_period.start_date
                        cutoff_end = pay_period.end_date
                        if use_attendance_sheets and align_cutoff_to_sheets and selected_sheet_ids:
                            sheet_qs = AttendanceSheet.objects.filter(id__in=selected_sheet_ids)
                            starts = [s.period_start for s in sheet_qs if s.period_start]
                            ends = [s.period_end for s in sheet_qs if s.period_end]
                            if starts and ends:
                                cutoff_start = min(starts)
                                cutoff_end = max(ends)

                        if use_attendance_sheets and not selected_sheet_ids:
                            messages.warning(
                                request,
                                'No attendance sheets selected. Compute will auto-match sheets that overlap the cutoff.',
                            )

                        run = PayrollRun.objects.create(
                            pay_period=pay_period,
                            cutoff_start=cutoff_start,
                            cutoff_end=cutoff_end,
                            status='draft',
                            use_attendance_sheets=use_attendance_sheets,
                            attendance_sheet_ids=selected_sheet_ids,
                        )
                        if use_attendance_sheets and selected_sheet_ids:
                            messages.success(
                                request,
                                (
                                    f'Payroll run #{run.id} created using {len(selected_sheet_ids)} '
                                    f'attendance sheet(s). Click "Compute" to calculate.'
                                ),
                            )
                        elif use_attendance_sheets:
                            messages.success(
                                request,
                                (
                                    f'Payroll run #{run.id} created. Attendance deductions will use sheets '
                                    f'overlapping {cutoff_start}–{cutoff_end}. Click "Compute" to calculate.'
                                ),
                            )
                        else:
                            messages.success(
                                request,
                                (
                                    f'Payroll run #{run.id} created without attendance-sheet deductions. '
                                    f'Click "Compute" to calculate.'
                                ),
                            )
            except PayPeriod.DoesNotExist:
                messages.error(request, 'Invalid pay period.')
        else:
            messages.error(request, 'Please select a pay period.')
        return redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")

    if action == 'compute_payroll':
        run_id = request.POST.get('run_id')
        if run_id:
            try:
                run = PayrollRun.objects.get(pk=run_id)
                if run.status != 'draft':
                    messages.warning(request, 'Only draft runs can be computed.')
                else:
                    from .payroll_attendance import load_attendance_deductions_by_employee
                    from .payroll_calculator import get_payroll_deductions
                    from .payroll_register import (
                        classify_holiday_days,
                        compute_register_earnings,
                        holidays_in_cutoff,
                    )

                    employees = Employee.objects.filter(
                        Q(termination_date__isnull=True) | Q(termination_date__gt=run.cutoff_end)
                    ).select_related('company')
                    run.lines.all().delete()

                    if run.use_attendance_sheets:
                        explicit_ids = list(run.attendance_sheet_ids or [])
                        att_by_employee, att_sheet_ids, unmapped_entries = (
                            load_attendance_deductions_by_employee(
                                run.cutoff_start,
                                run.cutoff_end,
                                sheet_ids=explicit_ids if explicit_ids else None,
                            )
                        )
                    else:
                        att_by_employee, att_sheet_ids, unmapped_entries = {}, [], 0

                    holiday_counts = classify_holiday_days(
                        holidays_in_cutoff(run.cutoff_start, run.cutoff_end)
                    )

                    computed_count = 0
                    attendance_applied_count = 0
                    for emp in employees:
                        att = att_by_employee.get(emp.id) or {}
                        undertime_minutes = int(att.get('undertime_minutes') or 0)
                        undertime_hours = Decimal(str(att.get('undertime_hours') or 0))
                        undertime_deduction = Decimal(str(att.get('undertime_deduction') or 0)).quantize(Decimal('0.01'))
                        absent_days = int(att.get('absent_days') or 0)
                        absence_deduction = Decimal(str(att.get('absence_deduction') or 0)).quantize(Decimal('0.01'))
                        # Register base already excludes LWP days; undertime is the late/UT money column.
                        attendance_deduction = undertime_deduction
                        employee_sheet_ids = list(att.get('attendance_sheet_ids') or [])

                        earnings = compute_register_earnings(
                            emp,
                            run.cutoff_start,
                            run.cutoff_end,
                            lwp_days=absent_days,
                            holiday_counts=holiday_counts,
                        )
                        # Prefer sheet-derived absence peso for display; days already reduce base.
                        if absent_days and not absence_deduction:
                            absence_deduction = (
                                earnings['daily_rate'] * Decimal(absent_days)
                            ).quantize(Decimal('0.01'))

                        base_pay = earnings['base_pay']
                        overtime_pay = earnings['overtime_pay']
                        holiday_pay = earnings['holiday_pay']
                        total_regular = earnings['regular_hours']
                        total_overtime = earnings['overtime_hours']
                        gross_pay = earnings['gross_pay']
                        hourly_rate = earnings['hourly_rate']

                        tax = Decimal('0.00')
                        configured = get_payroll_deductions(
                            emp, gross_pay, run.cutoff_start, run.cutoff_end,
                        )
                        philhealth = configured['philhealth']
                        sss = configured['sss']
                        hdmf = configured['hdmf']
                        sss_loan = configured['sss_loan']
                        hdmf_loan = configured['hdmf_loan']
                        other_deductions = configured['other']
                        statutory = configured['statutory']
                        voluntary = configured['voluntary']
                        configured_total = configured['total']

                        if undertime_deduction > 0 or absent_days > 0:
                            attendance_applied_count += 1

                        # Register TOTAL (-) = contribs + loans + late/UT (LWP already in base days).
                        total_deductions = configured_total + undertime_deduction
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
                                'daily_rate': float(earnings['daily_rate']),
                                'hourly_rate': float(hourly_rate),
                                'sil_on_hand': float(earnings['sil_on_hand']),
                                'reg_days': int(earnings['reg_days']),
                                'lwp_days': int(earnings['lwp_days']),
                                'total_days': int(earnings['total_days']),
                                'reg_total': float(earnings['reg_total']),
                                'ot_reg_hours': float(earnings['ot_reg_hours']),
                                'ot_reg_amount': float(earnings['ot_reg_amount']),
                                'ot_sun_hours': float(earnings['ot_sun_hours']),
                                'ot_sun_amount': float(earnings['ot_sun_amount']),
                                'ot_total_hours': float(earnings['ot_total_hours']),
                                'ot_total_amount': float(earnings['ot_total_amount']),
                                'snwd_days': int(earnings['snwd_days']),
                                'snwd_amount': float(earnings['snwd_amount']),
                                'snw_sun_days': int(earnings['snw_sun_days']),
                                'snw_sun_amount': float(earnings['snw_sun_amount']),
                                'rh_days': int(earnings['rh_days']),
                                'rh_amount': float(earnings['rh_amount']),
                                'gross_pay': float(gross_pay),
                                'tax': float(tax),
                                'philhealth': float(philhealth),
                                'sss': float(sss),
                                'hdmf': float(hdmf),
                                'sss_loan': float(sss_loan),
                                'hdmf_loan': float(hdmf_loan),
                                'other_deductions': float(other_deductions),
                                'statutory': float(statutory),
                                'voluntary': float(voluntary),
                                'configured_deductions': float(configured_total),
                                'deduction_items': configured.get('items') or {},
                                'undertime_minutes': undertime_minutes,
                                'undertime_hours': float(undertime_hours),
                                'undertime_deduction': float(undertime_deduction),
                                'absent_days': absent_days,
                                'absence_deduction': float(absence_deduction),
                                'attendance_deduction': float(attendance_deduction),
                                'attendance_sheet_ids': employee_sheet_ids,
                            },
                            regular_hours=total_regular,
                            overtime_hours=total_overtime,
                            ot_reg_hours=earnings['ot_reg_hours'],
                            ot_sun_hours=earnings['ot_sun_hours'],
                            holiday_pay=holiday_pay,
                        )
                        computed_count += 1

                    run.status = 'computed'
                    run.save()
                    if run.use_attendance_sheets:
                        messages.success(
                            request,
                            (
                                f'Payroll run #{run.id} computed for {computed_count} employee(s). '
                                f'Attendance deductions applied to {attendance_applied_count} employee(s) '
                                f'from {len(att_sheet_ids)} biometric sheet(s).'
                            ),
                        )
                        if not att_sheet_ids:
                            messages.warning(
                                request,
                                'No biometric attendance sheets were used for this run. '
                                'Undertime and absence deductions were ₱0 for all employees.',
                            )
                        elif unmapped_entries:
                            messages.warning(
                                request,
                                f'{unmapped_entries} punch-sheet entr'
                                f'{"y was" if unmapped_entries == 1 else "ies were"} '
                                'not linked to an employee and were skipped for payroll deductions.',
                            )
                    else:
                        messages.success(
                            request,
                            (
                                f'Payroll run #{run.id} computed for {computed_count} employee(s) '
                                f'without attendance-sheet deductions.'
                            ),
                        )
            except PayrollRun.DoesNotExist:
                messages.error(request, 'Run not found.')
            except Exception as exc:
                messages.error(request, f'Compute failed: {exc}')
        return redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")

    # ---------- SAVE OVERTIME HOURS ----------
    if action == 'save_payroll_overtime':
        run_id = request.POST.get('run_id')
        if not run_id:
            messages.error(request, 'Payroll run is required.')
            return redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")
        try:
            run = PayrollRun.objects.prefetch_related('lines__employee').get(pk=run_id)
            if run.status != 'computed':
                messages.warning(request, 'Overtime can only be edited on computed runs.')
                return redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")

            from .payroll_calculator import get_payroll_deductions
            from .payroll_register import ot_amounts_from_hours

            updated = 0
            for line in run.lines.all():
                reg_raw = request.POST.get(f'ot_reg_hours_{line.id}')
                sun_raw = request.POST.get(f'ot_sun_hours_{line.id}')
                if reg_raw is None and sun_raw is None:
                    continue
                try:
                    ot_reg = Decimal(reg_raw if reg_raw not in (None, '') else line.ot_reg_hours or 0)
                    ot_sun = Decimal(sun_raw if sun_raw not in (None, '') else line.ot_sun_hours or 0)
                except Exception:
                    messages.error(request, f'Invalid overtime hours for {line.employee.full_name}.')
                    return redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")
                if ot_reg < 0 or ot_sun < 0:
                    messages.error(request, 'Overtime hours cannot be negative.')
                    return redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")

                bd = dict(line.breakdown or {})
                hourly = Decimal(str(bd.get('hourly_rate') or 0))
                if not hourly:
                    daily = Decimal(str(bd.get('daily_rate') or estimated_daily_rate(line.employee)))
                    hourly = (daily / Decimal('8')).quantize(Decimal('0.01')) if daily else Decimal('0')

                ot = ot_amounts_from_hours(ot_reg, ot_sun, hourly)
                base_pay = Decimal(str(bd.get('base_pay') or 0)).quantize(Decimal('0.01'))
                holiday_pay = Decimal(str(bd.get('holiday_pay') or line.holiday_pay or 0)).quantize(Decimal('0.01'))
                gross_pay = (base_pay + ot['overtime_pay'] + holiday_pay).quantize(Decimal('0.01'))

                configured = get_payroll_deductions(
                    line.employee, gross_pay, run.cutoff_start, run.cutoff_end,
                )
                undertime_deduction = Decimal(str(bd.get('undertime_deduction') or 0)).quantize(Decimal('0.01'))
                total_deductions = (configured['total'] + undertime_deduction).quantize(Decimal('0.01'))
                net_pay = (gross_pay - total_deductions).quantize(Decimal('0.01'))

                bd.update({
                    'hourly_rate': float(hourly),
                    'overtime_pay': float(ot['overtime_pay']),
                    'overtime_hours': float(ot['overtime_hours']),
                    'ot_reg_hours': float(ot['ot_reg_hours']),
                    'ot_reg_amount': float(ot['ot_reg_amount']),
                    'ot_sun_hours': float(ot['ot_sun_hours']),
                    'ot_sun_amount': float(ot['ot_sun_amount']),
                    'ot_total_hours': float(ot['ot_total_hours']),
                    'ot_total_amount': float(ot['ot_total_amount']),
                    'gross_pay': float(gross_pay),
                    'philhealth': float(configured['philhealth']),
                    'sss': float(configured['sss']),
                    'hdmf': float(configured['hdmf']),
                    'sss_loan': float(configured['sss_loan']),
                    'hdmf_loan': float(configured['hdmf_loan']),
                    'other_deductions': float(configured['other']),
                    'statutory': float(configured['statutory']),
                    'voluntary': float(configured['voluntary']),
                    'configured_deductions': float(configured['total']),
                    'deduction_items': configured.get('items') or {},
                    'attendance_deduction': float(undertime_deduction),
                })

                line.ot_reg_hours = ot['ot_reg_hours']
                line.ot_sun_hours = ot['ot_sun_hours']
                line.overtime_hours = ot['overtime_hours']
                line.gross_pay = gross_pay
                line.total_deductions = total_deductions
                line.net_pay = net_pay
                line.breakdown = bd
                line.save(update_fields=[
                    'ot_reg_hours', 'ot_sun_hours', 'overtime_hours',
                    'gross_pay', 'total_deductions', 'net_pay', 'breakdown', 'updated_at',
                ])
                updated += 1

            messages.success(request, f'Saved overtime for {updated} employee(s) on run #{run.id}.')
        except PayrollRun.DoesNotExist:
            messages.error(request, 'Run not found.')
        except Exception as exc:
            messages.error(request, f'Could not save overtime: {exc}')
        return redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")

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
        return redirect(f"{reverse('hr_dashboard')}?tab=approvalsTab")

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
        return redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")

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
        return redirect(f"{reverse('hr_dashboard')}?tab=deductionsTab")

    # ---------- ASSIGN DEDUCTION TO EMPLOYEE(S) ----------
    if action == 'assign_deduction':
        scope = (request.POST.get('employee_scope') or 'selected').strip().lower()
        employee_ids = request.POST.getlist('employee_ids')
        config_ids = request.POST.getlist('config_ids')
        # Backward-compatible single fields
        if not config_ids and request.POST.get('config_id'):
            config_ids = [request.POST.get('config_id')]
        if scope == 'selected' and not employee_ids and request.POST.get('employee_id'):
            employee_ids = [request.POST.get('employee_id')]

        amount = request.POST.get('amount', '0')
        total_remaining = request.POST.get('total_remaining', '0') or '0'
        pay_period_id = request.POST.get('pay_period_id')

        try:
            if not config_ids:
                messages.error(request, 'Select at least one deduction to assign.')
                return redirect(f"{reverse('hr_dashboard')}?tab=deductionsTab")
            if not pay_period_id:
                messages.error(request, 'Select a pay period for this deduction.')
                return redirect(f"{reverse('hr_dashboard')}?tab=deductionsTab")

            pay_period = PayPeriod.objects.get(pk=pay_period_id)
            period_start = pay_period.start_date
            period_end = pay_period.end_date

            configs = list(DeductionConfig.objects.filter(pk__in=config_ids, is_active=True))
            if not configs:
                messages.error(request, 'No valid deductions selected.')
                return redirect(f"{reverse('hr_dashboard')}?tab=deductionsTab")

            if scope == 'all':
                employees = list(
                    Employee.objects.filter(
                        Q(termination_date__isnull=True) | Q(termination_date__gte=period_start)
                    ).order_by('last_name', 'first_name')
                )
            else:
                if not employee_ids:
                    messages.error(request, 'Select at least one employee, or choose All employees.')
                    return redirect(f"{reverse('hr_dashboard')}?tab=deductionsTab")
                employees = list(
                    Employee.objects.filter(pk__in=employee_ids).order_by('last_name', 'first_name')
                )
                if not employees:
                    messages.error(request, 'No valid employees selected.')
                    return redirect(f"{reverse('hr_dashboard')}?tab=deductionsTab")

            amount_dec = Decimal(amount)
            remaining_dec = Decimal(total_remaining)

            created = 0
            skipped = 0
            to_create = []
            for emp in employees:
                for config in configs:
                    already = EmployeeDeduction.objects.filter(
                        employee=emp,
                        deduction_config=config,
                        start_date=period_start,
                        end_date=period_end,
                    ).exists()
                    if already:
                        skipped += 1
                        continue
                    to_create.append(
                        EmployeeDeduction(
                            employee=emp,
                            deduction_config=config,
                            amount=amount_dec,
                            start_date=period_start,
                            end_date=period_end,
                            total_remaining=remaining_dec,
                        )
                    )
                    created += 1

            if to_create:
                EmployeeDeduction.objects.bulk_create(to_create)

            period_label = f'{period_start} – {period_end}'
            if created:
                messages.success(
                    request,
                    f'Created {created} deduction assignment(s) for period {period_label}'
                    + (f' ({skipped} already assigned, skipped).' if skipped else '.'),
                )
            elif skipped:
                messages.warning(
                    request,
                    f'No new assignments created — {skipped} already assigned for period {period_label}.',
                )
            else:
                messages.warning(request, 'No assignments were created.')
        except PayPeriod.DoesNotExist:
            messages.error(request, 'Invalid pay period.')
        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect(f"{reverse('hr_dashboard')}?tab=deductionsTab")

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
        return redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")

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
        return redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")

    # fallback
    return redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")

def _payroll_dashboard_context():
    pay_periods = PayPeriod.objects.all().order_by('-start_date')
    runs = PayrollRun.objects.select_related('pay_period').prefetch_related(
        'lines__employee',
    ).annotate(
        employee_count=Count('lines', distinct=True),
        total_gross=Sum('lines__gross_pay'),
        total_net=Sum('lines__net_pay'),
    ).order_by('-created_at')
    attendance_sheets = AttendanceSheet.objects.all().order_by('-uploaded_at', '-id')
    sheet_title_by_id = {sheet.id: sheet.title for sheet in attendance_sheets}
    for run in runs:
        ids = list(run.attendance_sheet_ids or [])
        run.attendance_sheet_labels = [
            sheet_title_by_id.get(sheet_id, f'Sheet #{sheet_id}') for sheet_id in ids
        ]
    deduction_configs = DeductionConfig.objects.filter(is_active=True)
    assigned_deductions = EmployeeDeduction.objects.select_related('employee', 'deduction_config').all()
    tax_brackets = TaxBracket.objects.filter(tax_type='withholding').order_by('effective_date', 'min_amount')
    return {
        'pay_periods': pay_periods,
        'runs': runs,
        'attendance_sheets': attendance_sheets,
        'deduction_configs': deduction_configs,
        'assigned_deductions': assigned_deductions,
        'tax_brackets': tax_brackets,
    }


@require_dashboard('hr_dashboard')
def payroll_dashboard(request):
    """Payroll lives inside HR; keep URL for bookmarks/legacy workspace accounts."""
    return redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")


def _payroll_register_run_or_error(request, run_id):
    try:
        run = PayrollRun.objects.select_related('pay_period').prefetch_related(
            'lines__employee',
        ).get(pk=run_id)
    except PayrollRun.DoesNotExist:
        return None, HttpResponse('Payroll run not found.', status=404)
    if run.status == 'draft':
        messages.error(request, 'Compute the payroll run before downloading the register.')
        return None, redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")
    if run.status not in ('computed', 'approved', 'disbursed'):
        messages.error(request, 'This payroll run cannot be exported.')
        return None, redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")
    if not run.lines.exists():
        messages.error(request, 'This payroll run has no employee lines to export.')
        return None, redirect(f"{reverse('hr_dashboard')}?tab=payrunsTab")
    return run, None


@require_dashboard('hr_dashboard')
def download_payroll_register_pdf(request, run_id):
    run, err = _payroll_register_run_or_error(request, run_id)
    if err is not None:
        return err
    from .payroll_register import build_payroll_register
    from .payroll_register_pdf import build_payroll_register_pdf

    register = build_payroll_register(run)
    pdf_bytes = build_payroll_register_pdf(register)
    filename = f"{register['meta']['filename_stem']}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@require_dashboard('hr_dashboard')
def download_payroll_register_xlsx(request, run_id):
    run, err = _payroll_register_run_or_error(request, run_id)
    if err is not None:
        return err
    from .payroll_register import build_payroll_register
    from .payroll_register_xlsx import build_payroll_register_xlsx

    register = build_payroll_register(run)
    xlsx_bytes = build_payroll_register_xlsx(register)
    filename = f"{register['meta']['filename_stem']}.xlsx"
    response = HttpResponse(
        xlsx_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def purchase_order_pdf(request):
    """Generate a Long Bond (8.5Ã—13) Purchase Order PDF via ReportLab."""
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
                messages.success(request, f'Account "{code} â€“ {name}" created.')
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
                    messages.success(request, f'Payment of â‚±{amount:.2f} recorded against {invoice.invoice_number}.')
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
                    messages.success(request, f'Payment of â‚±{amount:.2f} recorded against {bill.bill_number}.')
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
                    messages.success(request, f'{txn.get_transaction_type_display()} of â‚±{amount:.2f} recorded.')
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
                    messages.success(request, f'Payroll expense of â‚±{amount:.2f} recorded.')
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
            'material_borrows': MaterialBorrow.objects.prefetch_related('lines').all()[:8],
            'inventory_items': InventoryItem.objects.order_by('name'),
            'repair_report_count': ServiceRepairReport.objects.count(),
            'material_borrow_count': MaterialBorrow.objects.count(),
            'official_business_forms': OfficialBusinessForm.objects.all()[:8],
            'official_business_count': OfficialBusinessForm.objects.count(),
            'job_orders': JobOrder.objects.prefetch_related('assignees', 'idle_periods').all()[:8],
            'job_order_count': JobOrder.objects.count(),
            'next_job_order_number': JobOrder.generate_job_order_number(),
            'travel_order_forms': TravelOrderForm.objects.all()[:8],
            'travel_order_count': TravelOrderForm.objects.count(),
            'active_employees_for_jo': Employee.objects.filter(termination_date__isnull=True).order_by(
                'last_name', 'first_name',
            ),
            'employees': Employee.objects.filter(termination_date__isnull=True).select_related('position').order_by(
                'last_name', 'first_name',
            ),
            'next_report_number': ServiceRepairReport.generate_report_number(),
            'next_borrow_number': MaterialBorrow.generate_borrow_number(),
            **_build_idle_days_report(request),
        }
    )


@login_required
@require_POST
def create_service_repair_report(request):
    required = ('report_date', 'customer_name', 'equipment', 'complaint')
    if not all(request.POST.get(field, '').strip() for field in required):
        messages.error(request, 'Please complete all required Service Repair Report fields.')
        return redirect('services_dashboard')
    try:
        ServiceRepairReport.objects.create(
            report_number=request.POST.get('report_number', '').strip() or ServiceRepairReport.generate_report_number(),
            report_date=request.POST['report_date'],
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


@require_dashboard('services_dashboard')
@require_POST
def create_job_order(request):
    required = ('date_filed', 'job_description')
    if not all(request.POST.get(field, '').strip() for field in required):
        messages.error(request, 'Please complete all required Job Order fields.')
        return _job_order_redirect()

    assignee_ids = [aid for aid in request.POST.getlist('assignee_ids') if aid.strip()]
    free_text_names = [
        name.strip()
        for name in request.POST.getlist('assignee_names')
        if name.strip()
    ]
    coverage_start = parse_date(request.POST.get('coverage_start', '').strip() or '')
    coverage_end = parse_date(request.POST.get('coverage_end', '').strip() or '')
    if coverage_start and coverage_end and coverage_end < coverage_start:
        messages.error(request, 'Coverage end must be on or after coverage start.')
        return _job_order_redirect()

    dates_covered_lines = [
        date_value.strip()
        for date_value in request.POST.getlist('dates_covered')
        if date_value.strip()
    ]
    if coverage_start and coverage_end:
        dates_covered = f'{coverage_start.isoformat()}\n{coverage_end.isoformat()}'
    elif coverage_start:
        dates_covered = coverage_start.isoformat()
    elif coverage_end:
        dates_covered = coverage_end.isoformat()
    else:
        dates_covered = '\n'.join(dates_covered_lines)

    try:
        order = JobOrder.objects.create(
            job_order_number=request.POST.get('job_order_number', '').strip() or JobOrder.generate_job_order_number(),
            names='\n'.join(free_text_names),
            date_filed=request.POST['date_filed'],
            dates_covered=dates_covered,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            area_assignment=request.POST.get('area_assignment', '').strip(),
            job_description=request.POST['job_description'].strip(),
            prepared_by=request.POST.get('prepared_by', '').strip(),
            noted_by=request.POST.get('noted_by', '').strip(),
            approved_by=request.POST.get('approved_by', '').strip(),
        )
        if assignee_ids:
            employees = Employee.objects.filter(
                pk__in=assignee_ids, termination_date__isnull=True,
            )
            order.assignees.set(employees)
            order.sync_legacy_text_fields()
        messages.success(request, 'Job Order saved successfully.')
    except Exception as exc:
        messages.error(request, f'Could not save job order: {exc}')
    return _job_order_redirect()


@login_required
@require_POST
def create_material_borrow(request):
    required = ('date_borrowed', 'borrower_name')
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
            borrow_number=request.POST.get('borrow_number', '').strip() or MaterialBorrow.generate_borrow_number(),
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


@require_dashboard('services_dashboard')
@require_POST
def create_travel_order_form(request):
    required = ('travel_date', 'driver_name')
    if not all(request.POST.get(field, '').strip() for field in required):
        messages.error(request, 'Please complete all required Travel Order Form fields.')
        return _travel_order_redirect()

    travel_with = '\n'.join(
        name.strip()
        for name in request.POST.getlist('travel_with')
        if name.strip()
    )
    departure_time = request.POST.get('departure_time', '').strip() or None
    try:
        TravelOrderForm.objects.create(
            travel_date=request.POST['travel_date'],
            driver_name=request.POST['driver_name'].strip(),
            travel_with=travel_with,
            destination=request.POST.get('destination', '').strip(),
            purpose=request.POST.get('purpose', '').strip(),
            departure_time=departure_time,
            vehicle_plate=request.POST.get('vehicle_plate', '').strip(),
            fuel_allowance=request.POST.get('fuel_allowance', '').strip(),
            approved_by=request.POST.get('approved_by', '').strip(),
        )
        messages.success(request, 'Travel Order Form saved successfully.')
    except Exception as exc:
        messages.error(request, f'Could not save Travel Order Form: {exc}')
    return _travel_order_redirect()


def _official_business_redirect():
    return redirect(f"{reverse('services_dashboard')}?tab=officialBusinessTab")


def _job_order_redirect():
    return redirect(f"{reverse('services_dashboard')}?tab=jobOrderTab")


def _travel_order_redirect():
    return redirect(f"{reverse('services_dashboard')}?tab=travelOrderTab")


@require_dashboard('services_dashboard')
@require_POST
def create_official_business_form(request):
    required = ('name', 'application_date')
    if not all(request.POST.get(field, '').strip() for field in required):
        messages.error(request, 'Please complete all required Official Business Form fields.')
        return _official_business_redirect()

    ob_dates = '\n'.join(
        date_value.strip()
        for date_value in request.POST.getlist('ob_dates')
        if date_value.strip()
    )
    time_departure = request.POST.get('time_departure', '').strip() or None
    time_return = request.POST.get('time_return', '').strip() or None
    employee_name = request.POST['name'].strip()
    designation = request.POST.get('designation', '').strip()
    if not designation:
        matched_employee = next(
            (emp for emp in Employee.objects.select_related('position').all() if emp.full_name == employee_name),
            None,
        )
        if matched_employee:
            designation = matched_employee.position.title
    try:
        OfficialBusinessForm.objects.create(
            name=employee_name,
            designation=designation,
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
    return _official_business_redirect()


@require_dashboard('services_dashboard')
@require_POST
def approve_official_business_form(request, ob_id):
    ob_form = get_object_or_404(OfficialBusinessForm, pk=ob_id)
    ob_form.status = 'approved'
    ob_form.approved_at = timezone.now()
    ob_form.save(update_fields=['status', 'approved_at'])
    messages.success(request, f'Official Business Form for {ob_form.name} approved.')
    return _official_business_redirect()


@require_dashboard('services_dashboard')
@require_POST
def reject_official_business_form(request, ob_id):
    ob_form = get_object_or_404(OfficialBusinessForm, pk=ob_id)
    ob_form.status = 'rejected'
    ob_form.approved_at = timezone.now()
    ob_form.save(update_fields=['status', 'approved_at'])
    messages.success(request, f'Official Business Form for {ob_form.name} rejected.')
    return _official_business_redirect()


@login_required
@require_POST
def create_delivery_receipt(request):
    required = ('receipt_date', 'delivered_to')
    if not all(request.POST.get(field, '').strip() for field in required):
        messages.error(request, 'Please complete all required Delivery Receipt fields.')
        return redirect(f"{reverse('sales_dashboard')}?tab=delivery-receipt-tab")

    descriptions = request.POST.getlist('dr_item_description')
    quantities = request.POST.getlist('dr_item_quantity')
    units = request.POST.getlist('dr_item_unit')
    unit_prices = request.POST.getlist('dr_item_unit_price')
    inventory_ids = request.POST.getlist('dr_item_inventory')

    lines = []
    for index, description in enumerate(descriptions):
        description = description.strip()
        if not description:
            continue
        try:
            quantity = Decimal(quantities[index]) if index < len(quantities) and quantities[index].strip() else Decimal('1')
        except (InvalidOperation, IndexError):
            quantity = Decimal('1')
        try:
            unit_price = Decimal(unit_prices[index]) if index < len(unit_prices) and unit_prices[index].strip() else Decimal('0')
        except (InvalidOperation, IndexError):
            unit_price = Decimal('0')
        unit = units[index].strip() if index < len(units) else 'pcs'
        inventory_id = inventory_ids[index].strip() if index < len(inventory_ids) else ''
        inventory_item = None
        if inventory_id.isdigit():
            inventory_item = InventoryItem.objects.filter(pk=int(inventory_id)).first()
        lines.append({
            'inventory_item': inventory_item,
            'description': description,
            'quantity': quantity,
            'unit': unit or 'pcs',
            'unit_price': unit_price,
        })

    if not lines:
        messages.error(request, 'Please add at least one article to the delivery receipt.')
        return redirect(f"{reverse('sales_dashboard')}?tab=delivery-receipt-tab")

    try:
        receipt = DeliveryReceipt.objects.create(
            receipt_number=request.POST.get('receipt_number', '').strip() or DeliveryReceipt.generate_receipt_number(),
            receipt_date=request.POST['receipt_date'],
            delivered_to=request.POST['delivered_to'].strip(),
            tin=request.POST.get('tin', '').strip(),
            po_number=request.POST.get('po_number', '').strip(),
            address=request.POST.get('address', '').strip(),
            terms=request.POST.get('terms', '').strip(),
            certified_by=request.POST.get('certified_by', '').strip(),
            delivered_by=request.POST.get('delivered_by', '').strip(),
            received_by=request.POST.get('received_by', '').strip(),
        )
        DeliveryReceiptLine.objects.bulk_create([
            DeliveryReceiptLine(delivery_receipt=receipt, **line)
            for line in lines
        ])
        messages.success(request, 'Delivery Receipt saved successfully.')
    except Exception as exc:
        messages.error(request, f'Could not save Delivery Receipt: {exc}')
    return redirect(f"{reverse('sales_dashboard')}?tab=delivery-receipt-tab")


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
    'delivery_receipt': [
        ('Receipt No.', 'receipt_number'),
        ('Date', 'receipt_date'),
        ('Delivered To', 'delivered_to'),
        ('TIN', 'tin'),
        ('P.O. No.', 'po_number'),
        ('Address', 'address'),
        ('Terms', 'terms'),
        ('Certified by', 'certified_by'),
        ('Delivered by', 'delivered_by'),
        ('Received by (Customer)', 'received_by'),
    ],
    'travel': [
        ('Date', 'travel_date'),
        ("Driver's Name", 'driver_name'),
        ('Travel with', 'travel_with_display'),
        ('Venue/Destination', 'destination'),
        ('Purpose of Travel', 'purpose'),
        ('Departure Time', 'departure_time'),
        ('Vehicle / Plate No.', 'vehicle_plate'),
        ('Fuel Allowance (PO# Amount/Liters)', 'fuel_allowance'),
        ('Issued by', 'issued_by_display'),
        ('Approved by', 'approved_by'),
    ],
}


def _build_idle_days_report(request):
    """Build report rows for job-order idle periods (report-only; no payroll impact)."""
    idle_from = parse_date(request.GET.get('idle_from', '').strip() or '')
    idle_to = parse_date(request.GET.get('idle_to', '').strip() or '')
    idle_job_order_id = request.GET.get('idle_job_order', '').strip()
    idle_employee_id = request.GET.get('idle_employee', '').strip()

    periods = JobOrderIdlePeriod.objects.select_related('job_order').prefetch_related(
        'job_order__assignees',
    )
    if idle_job_order_id:
        periods = periods.filter(job_order_id=idle_job_order_id)
    if idle_from:
        periods = periods.filter(end_date__gte=idle_from)
    if idle_to:
        periods = periods.filter(start_date__lte=idle_to)

    # employee_id -> {job_order, days set, ranges list, employee}
    buckets = {}
    jobs_affected = set()

    for period in periods:
        period_days = set(period.idle_days())
        if idle_from or idle_to:
            filtered = set()
            for day in period_days:
                if idle_from and day < idle_from:
                    continue
                if idle_to and day > idle_to:
                    continue
                filtered.add(day)
            period_days = filtered
        if not period_days:
            continue

        assignees = list(period.job_order.assignees.all())
        if idle_employee_id:
            assignees = [e for e in assignees if str(e.pk) == idle_employee_id]
            if not assignees:
                continue

        jobs_affected.add(period.job_order_id)
        range_label = f'{period.start_date.isoformat()} – {period.end_date.isoformat()}'

        if not assignees:
            key = (period.job_order_id, None)
            bucket = buckets.setdefault(key, {
                'job_order': period.job_order,
                'employee': None,
                'days': set(),
                'ranges': [],
            })
            bucket['days'] |= period_days
            if range_label not in bucket['ranges']:
                bucket['ranges'].append(range_label)
            continue

        for emp in assignees:
            key = (period.job_order_id, emp.pk)
            bucket = buckets.setdefault(key, {
                'job_order': period.job_order,
                'employee': emp,
                'days': set(),
                'ranges': [],
            })
            bucket['days'] |= period_days
            if range_label not in bucket['ranges']:
                bucket['ranges'].append(range_label)

    rows = []
    total_idle_days = 0
    total_estimated_waste = Decimal('0.00')

    for bucket in buckets.values():
        day_count = len(bucket['days'])
        emp = bucket['employee']
        daily_rate = estimated_daily_rate(emp) if emp else Decimal('0.00')
        estimated_waste = (daily_rate * day_count).quantize(Decimal('0.01'))
        total_idle_days += day_count
        total_estimated_waste += estimated_waste
        rows.append({
            'job_order': bucket['job_order'],
            'employee': emp,
            'ranges': ', '.join(bucket['ranges']),
            'idle_day_count': day_count,
            'daily_rate': daily_rate,
            'estimated_waste': estimated_waste,
        })

    rows.sort(
        key=lambda r: (
            r['job_order'].job_order_number,
            (r['employee'].last_name if r['employee'] else ''),
            (r['employee'].first_name if r['employee'] else ''),
        )
    )

    return {
        'idle_report_rows': rows,
        'idle_total_days': total_idle_days,
        'idle_total_waste': total_estimated_waste,
        'idle_jobs_affected': len(jobs_affected),
        'idle_from': idle_from.isoformat() if idle_from else '',
        'idle_to': idle_to.isoformat() if idle_to else '',
        'idle_job_order_id': idle_job_order_id,
        'idle_employee_id': idle_employee_id,
        'idle_filter_job_orders': JobOrder.objects.order_by('-date_filed')[:200],
        'idle_filter_employees': Employee.objects.filter(termination_date__isnull=True).order_by(
            'last_name', 'first_name',
        ),
        'active_employees_for_jo': Employee.objects.filter(termination_date__isnull=True).order_by(
            'last_name', 'first_name',
        ),
    }


def _service_record_context(record, document_type):
    fields = []
    for label, attribute in SERVICE_FIELD_LABELS[document_type]:
        value = getattr(record, attribute)
        value = value() if callable(value) else value
        if isinstance(value, datetime):
            value = value.strftime('%B %d, %Y')
        elif isinstance(value, date):
            value = value.strftime('%B %d, %Y')
        elif isinstance(value, time):
            value = value.strftime('%I:%M %p').lstrip('0')
        fields.append((label, value or 'â€”'))
    return {'record': record, 'fields': fields, 'document_type': document_type}


def _borrow_record_context(record):
    context = _service_record_context(record, 'borrow')
    context['borrow_lines'] = record.lines.all()
    return context


def _delivery_receipt_record_context(record):
    context = _service_record_context(record, 'delivery_receipt')
    context['delivery_receipt_lines'] = record.lines.all()
    context['delivery_receipt_total'] = record.total_amount
    return context


@login_required
def view_service_repair_report(request, report_id):
    context = _service_record_context(
        get_object_or_404(ServiceRepairReport, pk=report_id), 'repair'
    )
    return render(
        request,
        'service_document_detail.html',
        _enrich_document_context(request, context, 'repair'),
    )


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
    order = get_object_or_404(
        JobOrder.objects.prefetch_related('assignees', 'idle_periods'),
        pk=order_id,
    )
    context = _service_record_context(order, 'job')
    context['idle_periods'] = order.idle_periods.all()
    context['idle_period_form'] = JobOrderIdlePeriodForm(job_order=order)
    context['idle_reason_choices'] = JobOrderIdlePeriod.REASON_CHOICES
    return render(
        request,
        'service_document_detail.html',
        _enrich_document_context(request, context, 'job'),
    )


@require_dashboard('services_dashboard')
def edit_job_order(request, order_id):
    order = get_object_or_404(JobOrder, pk=order_id)
    form = JobOrderForm(request.POST or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Job Order updated successfully.')
        return redirect('view_job_order', order_id=order.id)
    return render(request, 'service_document_form.html', {'form': form, 'record': order, 'document_type': 'job'})


@require_dashboard('services_dashboard')
@require_POST
def delete_job_order(request, order_id):
    get_object_or_404(JobOrder, pk=order_id).delete()
    messages.success(request, 'Job Order deleted.')
    return _job_order_redirect()


@require_dashboard('services_dashboard')
@require_POST
def add_job_order_idle_period(request, order_id):
    order = get_object_or_404(JobOrder, pk=order_id)
    form = JobOrderIdlePeriodForm(request.POST, job_order=order)
    if form.is_valid():
        period = form.save(commit=False)
        period.job_order = order
        period.save()
        messages.success(
            request,
            f'Idle period recorded: {period.start_date} – {period.end_date} '
            f'({period.idle_day_count} day(s), Sundays excluded).',
        )
    else:
        for field, errors in form.errors.items():
            label = 'Idle period' if field == '__all__' else field.replace('_', ' ').title()
            for error in errors:
                messages.error(request, f'{label}: {error}')
    return redirect('view_job_order', order_id=order.id)


@require_dashboard('services_dashboard')
@require_POST
def delete_job_order_idle_period(request, order_id, period_id):
    order = get_object_or_404(JobOrder, pk=order_id)
    period = get_object_or_404(JobOrderIdlePeriod, pk=period_id, job_order=order)
    period.delete()
    messages.success(request, 'Idle period removed.')
    return redirect('view_job_order', order_id=order.id)


@login_required
def view_official_business_form(request, ob_id):
    context = _service_record_context(
        get_object_or_404(OfficialBusinessForm, pk=ob_id), 'ob'
    )
    return render(
        request,
        'service_document_detail.html',
        _enrich_document_context(request, context, 'ob'),
    )


@require_dashboard('services_dashboard')
def edit_official_business_form(request, ob_id):
    ob_form = get_object_or_404(OfficialBusinessForm, pk=ob_id)
    form = OfficialBusinessFormForm(request.POST or None, instance=ob_form)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Official Business Form updated successfully.')
        return redirect('view_official_business_form', ob_id=ob_form.id)
    return render(request, 'service_document_form.html', {'form': form, 'record': ob_form, 'document_type': 'ob'})


@require_dashboard('services_dashboard')
@require_POST
def delete_official_business_form(request, ob_id):
    get_object_or_404(OfficialBusinessForm, pk=ob_id).delete()
    messages.success(request, 'Official Business Form deleted.')
    return _official_business_redirect()


@login_required
def view_travel_order_form(request, order_id):
    context = _service_record_context(
        get_object_or_404(TravelOrderForm, pk=order_id), 'travel'
    )
    return render(
        request,
        'service_document_detail.html',
        _enrich_document_context(request, context, 'travel'),
    )


@require_dashboard('services_dashboard')
def edit_travel_order_form(request, order_id):
    travel_order = get_object_or_404(TravelOrderForm, pk=order_id)
    form = TravelOrderFormForm(request.POST or None, instance=travel_order)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Travel Order Form updated successfully.')
        return redirect('view_travel_order_form', order_id=travel_order.id)
    return render(request, 'service_document_form.html', {
        'form': form,
        'record': travel_order,
        'document_type': 'travel',
    })


@require_dashboard('services_dashboard')
@require_POST
def delete_travel_order_form(request, order_id):
    get_object_or_404(TravelOrderForm, pk=order_id).delete()
    messages.success(request, 'Travel Order Form deleted.')
    return _travel_order_redirect()


@login_required
def view_delivery_receipt(request, receipt_id):
    context = _delivery_receipt_record_context(
        get_object_or_404(DeliveryReceipt.objects.prefetch_related('lines'), pk=receipt_id)
    )
    return render(
        request,
        'service_document_detail.html',
        _enrich_document_context(request, context, 'delivery_receipt'),
    )


@login_required
def edit_delivery_receipt(request, receipt_id):
    receipt = get_object_or_404(DeliveryReceipt, pk=receipt_id)
    form = DeliveryReceiptForm(request.POST or None, instance=receipt)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Delivery Receipt updated successfully.')
        return redirect('view_delivery_receipt', receipt_id=receipt.id)
    return render(request, 'service_document_form.html', {
        'form': form,
        'record': receipt,
        'document_type': 'delivery_receipt',
    })


@login_required
@require_POST
def delete_delivery_receipt(request, receipt_id):
    get_object_or_404(DeliveryReceipt, pk=receipt_id).delete()
    messages.success(request, 'Delivery Receipt deleted.')
    return redirect(f"{reverse('sales_dashboard')}?tab=delivery-receipt-tab")


@login_required
def view_material_borrow(request, borrow_id):
    context = _borrow_record_context(
        get_object_or_404(MaterialBorrow.objects.prefetch_related('lines'), pk=borrow_id)
    )
    return render(
        request,
        'service_document_detail.html',
        _enrich_document_context(request, context, 'borrow'),
    )


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


# ========== WATER BILLING ==========

WATER_DEFAULT_RATE = Decimal('20.00')
WATER_INSTALLATION_FEE = Decimal('5900.00')
WATER_INSTALLATION_PARTIAL = Decimal('3000.00')
WATER_DEFAULT_FIXED = Decimal('50.00')
WATER_DEFAULT_ENV = Decimal('10.00')
WATER_DEFAULT_MAINT = Decimal('15.00')
WATER_DEFAULT_RECONNECT_FEE = Decimal('500.00')


def _water_redirect(tab=''):
    url = reverse('water_billing_dashboard')
    return redirect(f'{url}?tab={tab}' if tab else url)


def _water_audit(request, action, entity_type, entity_id='', details=''):
    WaterAuditLog.objects.create(
        username=getattr(request.user, 'username', '') or '',
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id or ''),
        details=details or '',
    )


def _dec(value, default='0'):
    try:
        return Decimal(str(value or default).replace(',', '').strip() or default)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _water_parse_date(value, required=False):
    parsed = parse_date(str(value).strip()) if value else None
    if parsed:
        return parsed
    if required:
        raise ValueError('Invalid date.')
    return None


def _water_open_bills():
    return (
        WaterBill.objects.select_related('customer')
        .exclude(status__in=['paid', 'cancelled'])
        .filter(total_amount__gt=F('amount_paid'))
    )


def _water_annotate_outstanding(qs):
    money = DecimalField(max_digits=14, decimal_places=2)
    outstanding_sq = (
        WaterBill.objects.filter(customer_id=OuterRef('pk'))
        .exclude(status='cancelled')
        .values('customer_id')
        .annotate(
            total=Sum(
                ExpressionWrapper(
                    F('total_amount') - F('amount_paid'),
                    output_field=money,
                )
            )
        )
        .values('total')[:1]
    )
    return qs.annotate(
        annotated_outstanding=Greatest(
            Coalesce(Subquery(outstanding_sq, output_field=money), Value(Decimal('0.00')), output_field=money),
            Value(Decimal('0.00')),
            output_field=money,
        )
    )


def _water_months_unpaid_from_date(oldest):
    if not oldest:
        return 0
    today = date.today()
    months = (today.year - oldest.year) * 12 + (today.month - oldest.month)
    if today.day < oldest.day:
        months -= 1
    return max(months, 0)


def _water_paginate(qs, request, per_page=50):
    paginator = Paginator(qs, per_page)
    try:
        return paginator.page(request.GET.get('page') or 1)
    except (PageNotAnInteger, EmptyPage):
        return paginator.page(1)


def _water_paginate_param(qs, request, param='cpage', per_page=25):
    paginator = Paginator(qs, per_page)
    try:
        return paginator.page(request.GET.get(param) or 1)
    except (PageNotAnInteger, EmptyPage):
        return paginator.page(1)


def _water_normalize_tab(tab):
    if tab in ('readingsTab', 'billingTab'):
        return 'readingsBillingTab'
    allowed = {
        'overviewTab', 'customersTab', 'readingsBillingTab', 'paymentsTab',
        'arTab', 'disconnectTab', 'reportsTab', 'auditTab', 'helpTab',
    }
    return tab if tab in allowed else 'overviewTab'


def _water_pager_qs(request, drop=('tab', 'page', 'fragment', 'list_only')):
    params = request.GET.copy()
    for key in drop:
        params.pop(key, None)
    encoded = params.urlencode()
    return f'&{encoded}' if encoded else ''


def _water_overview_stats():
    today = date.today()
    month_start = today.replace(day=1)
    money = DecimalField(max_digits=14, decimal_places=2)
    active_customers = WaterCustomer.objects.filter(connection_status='active').count()
    disconnected = WaterCustomer.objects.filter(connection_status='disconnected').count()
    new_customers = WaterCustomer.objects.filter(registration_date__gte=month_start).count()
    total_customers = WaterCustomer.objects.count()

    month_consumption = (
        WaterMeterReading.objects.filter(reading_date__gte=month_start).aggregate(total=Sum('consumption'))['total']
        or 0
    )
    bills_generated = WaterBill.objects.filter(bill_date__gte=month_start).exclude(status='cancelled').count()
    totals = WaterBill.objects.exclude(status='cancelled').aggregate(
        billed=Coalesce(Sum('total_amount'), Value(0), output_field=money),
        paid=Coalesce(Sum('amount_paid'), Value(0), output_field=money),
    )
    billed_total = totals['billed'] or Decimal('0.00')
    paid_total = totals['paid'] or Decimal('0.00')
    outstanding = max(billed_total - paid_total, Decimal('0.00'))
    collection_rate = Decimal('0.00')
    if billed_total > 0:
        collection_rate = ((paid_total / billed_total) * Decimal('100')).quantize(Decimal('0.01'))

    reconnected = WaterServiceAction.objects.filter(
        action_type='reconnection', status='completed', action_date__gte=month_start,
    ).count()

    return {
        'total_customers': total_customers,
        'active_customers': active_customers,
        'active_connections': active_customers,
        'month_consumption': month_consumption,
        'bills_generated': bills_generated,
        'outstanding_balance': outstanding,
        'collection_rate': collection_rate,
        'new_customers': new_customers,
        'disconnected_accounts': disconnected,
        'reconnected_accounts': reconnected,
    }


WATER_REVENUE_PERIODS = {
    'week': 'This week',
    'month': 'This month',
    'year': 'This year',
}


def _water_revenue_period(request):
    period = (request.GET.get('revenue_period') or 'month').strip()
    if period not in WATER_REVENUE_PERIODS:
        period = 'month'
    return period


def _water_revenue_period_start(period):
    today = date.today()
    if period == 'week':
        return today - timedelta(days=today.weekday())
    if period == 'year':
        return today.replace(month=1, day=1)
    return today.replace(day=1)


def _water_revenue_by_method(period='month'):
    if period not in WATER_REVENUE_PERIODS:
        period = 'month'
    money = DecimalField(max_digits=14, decimal_places=2)
    start = _water_revenue_period_start(period)
    totals = WaterPayment.objects.filter(payment_date__gte=start).aggregate(
        cash=Coalesce(Sum('amount', filter=Q(payment_method='cash')), Value(0), output_field=money),
        gcash=Coalesce(Sum('amount', filter=Q(payment_method='gcash')), Value(0), output_field=money),
    )
    cash = totals['cash'] or Decimal('0.00')
    gcash = totals['gcash'] or Decimal('0.00')
    return {
        'revenue_period': period,
        'revenue_period_label': WATER_REVENUE_PERIODS[period],
        'revenue_cash': cash,
        'revenue_gcash': gcash,
        'revenue_collected': cash + gcash,
    }


def _water_revenue_from_request(request):
    return _water_revenue_by_method(_water_revenue_period(request))


def _water_filtered_customers(request):
    customer_q = request.GET.get('customer_q', '').strip()
    customer_zone = request.GET.get('customer_zone', '').strip()
    customer_status = request.GET.get('customer_status', '').strip()
    customers_qs = _water_annotate_outstanding(WaterCustomer.objects.select_related('zone'))
    if customer_q:
        customers_qs = customers_qs.filter(
            Q(account_number__icontains=customer_q)
            | Q(first_name__icontains=customer_q)
            | Q(last_name__icontains=customer_q)
            | Q(meter_number__icontains=customer_q)
            | Q(service_address__icontains=customer_q)
            | Q(contact_number__icontains=customer_q)
        )
    if customer_zone.isdigit():
        customers_qs = customers_qs.filter(zone_id=customer_zone)
    if customer_status:
        customers_qs = customers_qs.filter(connection_status=customer_status)
    return customers_qs, customer_q, customer_zone, customer_status


def _water_filtered_readings(request):
    reading_zone = request.GET.get('reading_zone', '').strip()
    readings_qs = WaterMeterReading.objects.select_related('customer', 'customer__zone', 'bill')
    if reading_zone.isdigit():
        readings_qs = readings_qs.filter(customer__zone_id=reading_zone)
    return readings_qs, reading_zone


def _water_all_customers_qs():
    return _water_annotate_outstanding(
        WaterCustomer.objects.annotate(
            last_current_reading=Subquery(
                WaterMeterReading.objects.filter(customer_id=OuterRef('pk'))
                .order_by('-reading_date', '-created_at')
                .values('current_reading')[:1]
            ),
            oldest_unpaid=Min(
                'bills__due_date',
                filter=~Q(bills__status__in=['paid', 'cancelled']),
            ),
        )
    ).order_by('account_number')


def _water_aging_buckets(unpaid_bills):
    aging_buckets = {
        'current': Decimal('0'), 'd1_30': Decimal('0'), 'd31_60': Decimal('0'),
        'd61_90': Decimal('0'), 'd90_plus': Decimal('0'),
    }
    today = date.today()
    for bill in unpaid_bills:
        days = (today - bill.due_date).days if bill.due_date else 0
        bal = bill.balance_due
        if days <= 0:
            aging_buckets['current'] += bal
        elif days <= 30:
            aging_buckets['d1_30'] += bal
        elif days <= 60:
            aging_buckets['d31_60'] += bal
        elif days <= 90:
            aging_buckets['d61_90'] += bal
        else:
            aging_buckets['d90_plus'] += bal
    return aging_buckets


def _water_disconnect_candidates():
    qs = _water_annotate_outstanding(
        WaterCustomer.objects.filter(
            connection_status__in=['active', 'for_disconnection', 'inactive'],
        ).annotate(
            oldest_unpaid=Min(
                'bills__due_date',
                filter=~Q(bills__status__in=['paid', 'cancelled']) & Q(bills__total_amount__gt=F('bills__amount_paid')),
            ),
        )
    ).order_by('account_number')
    candidates = []
    for customer in qs:
        months = _water_months_unpaid_from_date(getattr(customer, 'oldest_unpaid', None))
        if months < 3:
            continue
        customer.computed_months_unpaid = months
        customer.computed_monitor = _water_monitor_label(customer, months)
        candidates.append(customer)
        if len(candidates) >= 50:
            break
    return candidates


def _water_monitor_label(customer, months):
    status = customer.connection_status
    if status == 'disconnected':
        return 'Disconnected'
    if status == 'for_disconnection':
        return 'For disconnection'
    if months >= 3:
        return f'For disconnection ({months} months unpaid)'
    if months >= 1:
        suffix = 's' if months != 1 else ''
        return f'At risk ({months} month{suffix} unpaid)'
    outstanding = getattr(customer, 'annotated_outstanding', None) or Decimal('0.00')
    if outstanding > 0:
        return 'Current (unpaid under 1 month)'
    return 'Current – no unpaid balance'


def _water_tab_context(request, tab):
    ctx = {
        'active_tab': tab,
        'customer_types': WATER_CUSTOMER_TYPES,
        'connection_statuses': WATER_CONNECTION_STATUS,
        'payment_methods': WATER_PAYMENT_METHODS,
        'bill_statuses': WATER_BILL_STATUS,
        'service_action_types': WATER_SERVICE_ACTION_TYPES,
        'service_action_statuses': WATER_SERVICE_ACTION_STATUS,
        'default_rate': WATER_DEFAULT_RATE,
        'default_fixed': WATER_DEFAULT_FIXED,
        'default_env': WATER_DEFAULT_ENV,
        'default_maint': WATER_DEFAULT_MAINT,
        'default_reconnect_fee': WATER_DEFAULT_RECONNECT_FEE,
        'pager_tab': tab,
        'pager_qs': _water_pager_qs(request),
    }
    if tab == 'overviewTab':
        ctx['stats'] = _water_overview_stats()
        ctx.update(_water_revenue_from_request(request))
    elif tab == 'customersTab':
        customers_qs, customer_q, customer_zone, customer_status = _water_filtered_customers(request)
        page_obj = _water_paginate(customers_qs, request)
        ctx.update({
            'customers': page_obj,
            'page_obj': page_obj,
            'customer_q': customer_q,
            'customer_zone': customer_zone,
            'customer_status': customer_status,
            'water_zones': WaterZone.objects.order_by('name'),
            'next_account_number': WaterCustomer.generate_account_number(),
        })
    elif tab == 'readingsBillingTab':
        readings_qs, reading_zone = _water_filtered_readings(request)
        page_obj = _water_paginate(readings_qs, request)
        ctx.update({
            'all_customers': _water_all_customers_qs(),
            'readings': page_obj,
            'page_obj': page_obj,
            'reading_zone': reading_zone,
            'water_zones': WaterZone.objects.order_by('name'),
            'next_bill_number': WaterBill.generate_bill_number(),
        })
    elif tab == 'paymentsTab':
        page_obj = _water_paginate(
            WaterPayment.objects.select_related('customer', 'bill').all(),
            request,
        )
        ctx.update({
            'payments': page_obj,
            'page_obj': page_obj,
            'open_bills_for_payment': _water_open_bills(),
            'next_receipt_number': WaterPayment.generate_receipt_number(),
        })
        ctx.update(_water_revenue_from_request(request))
    elif tab == 'arTab':
        open_bills = list(_water_open_bills())
        page_obj = _water_paginate(open_bills, request)
        ctx.update({
            'unpaid_bills': page_obj,
            'page_obj': page_obj,
            'aging_buckets': _water_aging_buckets(open_bills),
        })
    elif tab == 'disconnectTab':
        page_obj = _water_paginate(
            WaterServiceAction.objects.select_related('customer').all(),
            request,
        )
        all_customers = list(_water_all_customers_qs())
        for customer in all_customers:
            customer.computed_months_unpaid = _water_months_unpaid_from_date(
                getattr(customer, 'oldest_unpaid', None)
            )
        ctx.update({
            'all_customers': all_customers,
            'disconnect_candidates': _water_disconnect_candidates(),
            'service_actions': page_obj,
            'page_obj': page_obj,
            'service_contracts': _water_paginate_param(
                WaterServiceContract.objects.select_related('customer').all(),
                request,
                param='cpage',
            ),
            'contract_application_statuses': WATER_CONTRACT_APPLICATION_STATUS,
            'contract_home_ownerships': WATER_CONTRACT_HOME_OWNERSHIP,
            'contract_classifications': WATER_CONTRACT_CLASSIFICATION,
            'contract_civil_statuses': WATER_CONTRACT_CIVIL_STATUS,
            'edit_contract': _water_get_edit_contract(request),
        })
    elif tab == 'reportsTab':
        report_type = request.GET.get('report', 'billing')
        page_obj = _water_paginate(_water_report_rows(report_type), request)
        ctx.update({
            'report_type': report_type,
            'report_rows': page_obj,
            'page_obj': page_obj,
        })
    elif tab == 'auditTab':
        page_obj = _water_paginate(WaterAuditLog.objects.all(), request)
        ctx.update({
            'audit_logs': page_obj,
            'page_obj': page_obj,
        })
    return ctx


WATER_TAB_TEMPLATES = {
    'overviewTab': 'includes/water_tab_overview.html',
    'customersTab': 'includes/water_tab_customers.html',
    'readingsBillingTab': 'includes/water_tab_readings.html',
    'paymentsTab': 'includes/water_tab_payments.html',
    'arTab': 'includes/water_tab_receivables.html',
    'disconnectTab': 'includes/water_tab_service.html',
    'reportsTab': 'includes/water_tab_reports.html',
    'auditTab': 'includes/water_tab_audit.html',
    'helpTab': 'includes/water_tab_help.html',
}


@require_dashboard('water_billing_dashboard')
def water_billing_dashboard(request):
    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
        handlers = {
            'create_customer': _water_create_customer,
            'create_reading': _water_create_reading,
            'create_bill': _water_create_bill,
            'generate_bill': _water_generate_bill_from_reading,
            'generate_all_bills': _water_generate_all_bills,
            'create_payment': _water_create_payment,
            'create_service_action': _water_create_service_action,
            'complete_service_action': _water_complete_service_action,
            'create_service_contract': _water_create_service_contract,
            'update_service_contract': _water_update_service_contract,
            'delete_customer': _water_delete_customer,
            'delete_reading': _water_delete_reading,
            'delete_bill': _water_delete_bill,
            'delete_payment': _water_delete_payment,
        }
        handler = handlers.get(action)
        if handler:
            return handler(request)
        messages.error(request, 'Unknown water billing action.')
        return _water_redirect()

    tab = _water_normalize_tab(request.GET.get('tab', '').strip())
    if request.GET.get('fragment') == '1':
        context = _water_tab_context(request, tab)
        template = WATER_TAB_TEMPLATES[tab]
        if tab == 'customersTab' and request.GET.get('list_only') == '1':
            template = 'includes/water_customer_list.html'
        elif tab == 'readingsBillingTab' and request.GET.get('list_only') == '1':
            template = 'includes/water_reading_list.html'
        return render(request, template, context)

    context = {
        'modules': MANAGEMENT_MODULES,
        'active_tab': tab,
        'loaded_tabs': {tab, 'overviewTab'},
    }
    if tab != 'overviewTab':
        context['stats'] = _water_overview_stats()
    context.update(_water_revenue_from_request(request))
    context.update(_water_tab_context(request, tab))
    return render(request, 'water_billing_dashboard.html', context)


def _water_report_rows(report_type):
    today = date.today()
    month_start = today.replace(day=1)
    if report_type == 'collection':
        return WaterPayment.objects.select_related('customer', 'bill').filter(payment_date__gte=month_start)
    if report_type == 'outstanding':
        return _water_open_bills()
    if report_type == 'consumption':
        return WaterMeterReading.objects.select_related('customer').filter(reading_date__gte=month_start)
    if report_type == 'customers':
        return WaterCustomer.objects.all()
    if report_type == 'disconnection':
        return WaterServiceAction.objects.select_related('customer').filter(action_type='disconnection')
    if report_type == 'reconnection':
        return WaterServiceAction.objects.select_related('customer').filter(action_type='reconnection')
    if report_type == 'readings':
        return WaterMeterReading.objects.select_related('customer').all()
    if report_type == 'daily_collection':
        return WaterPayment.objects.select_related('customer', 'bill').filter(payment_date=today)
    if report_type == 'revenue':
        return WaterPayment.objects.select_related('customer', 'bill').all()
    return WaterBill.objects.select_related('customer').filter(bill_date__gte=month_start)


def _water_resolve_zone(request):
    """Resolve zone from POST zone_id / zone_name. Optional; returns None if unset."""
    zone_id = request.POST.get('zone_id', '').strip()
    zone_name = request.POST.get('zone_name', '').strip().upper()
    if zone_id and zone_id != '__new__':
        return WaterZone.objects.filter(pk=zone_id).first()
    if zone_name:
        zone, _ = WaterZone.objects.get_or_create(name=zone_name)
        return zone
    return None


def _water_create_customer(request):
    required = ('first_name', 'last_name', 'meter_number')
    if not all(request.POST.get(f, '').strip() for f in required):
        messages.error(request, 'Please complete required customer fields.')
        return _water_redirect('customersTab')
    try:
        payment_choice = request.POST.get('installation_payment', 'full').strip().lower()
        if payment_choice == 'full':
            installation_paid = WATER_INSTALLATION_FEE
        elif payment_choice == 'partial':
            installation_paid = WATER_INSTALLATION_PARTIAL
        else:
            installation_paid = _dec(request.POST.get('installation_paid'), '0')
            if installation_paid < 0:
                installation_paid = Decimal('0.00')
            if installation_paid > WATER_INSTALLATION_FEE:
                installation_paid = WATER_INSTALLATION_FEE
        installment_balance = max(WATER_INSTALLATION_FEE - installation_paid, Decimal('0.00'))

        customer = WaterCustomer.objects.create(
            account_number=request.POST.get('account_number', '').strip() or WaterCustomer.generate_account_number(),
            first_name=request.POST['first_name'].strip().upper(),
            last_name=request.POST['last_name'].strip().upper(),
            service_address=request.POST.get('service_address', '').strip().upper(),
            contact_number=request.POST.get('contact_number', '').strip(),
            email=request.POST.get('email', '').strip(),
            customer_type=request.POST.get('customer_type', 'residential'),
            zone=_water_resolve_zone(request),
            meter_number=request.POST['meter_number'].strip().upper(),
            connection_status=request.POST.get('connection_status', 'active'),
            registration_date=_water_parse_date(request.POST.get('registration_date')) or date.today(),
            installment_balance=installment_balance,
            notes=request.POST.get('notes', '').strip(),
        )
        _water_audit(
            request,
            'Created customer',
            'WaterCustomer',
            customer.account_number,
            f'{customer.display_name} | install fee â‚±{WATER_INSTALLATION_FEE} paid â‚±{installation_paid} bal â‚±{installment_balance}',
        )
        messages.success(
            request,
            f'Customer {customer.account_number} registered. '
            f'Installation paid â‚±{installation_paid:.2f}; balance â‚±{installment_balance:.2f}.',
        )
    except Exception as exc:
        messages.error(request, f'Could not save customer: {exc}')
    return _water_redirect('customersTab')


def _water_update_customer(request, customer):
    required = ('first_name', 'last_name', 'meter_number')
    if not all(request.POST.get(f, '').strip() for f in required):
        messages.error(request, 'Please complete required customer fields.')
        return redirect('view_water_customer', customer_id=customer.id)
    try:
        customer.first_name = request.POST['first_name'].strip().upper()
        customer.last_name = request.POST['last_name'].strip().upper()
        customer.service_address = request.POST.get('service_address', '').strip().upper()
        customer.contact_number = request.POST.get('contact_number', '').strip()
        customer.email = request.POST.get('email', '').strip()
        customer.customer_type = request.POST.get('customer_type', customer.customer_type)
        customer.zone = _water_resolve_zone(request)
        customer.meter_number = request.POST['meter_number'].strip().upper()
        customer.connection_status = request.POST.get('connection_status', customer.connection_status)
        reg_date = _water_parse_date(request.POST.get('registration_date'))
        if reg_date:
            customer.registration_date = reg_date
        if 'installment_balance' in request.POST:
            bal = _dec(request.POST.get('installment_balance'), str(customer.installment_balance or 0))
            if bal < 0:
                bal = Decimal('0.00')
            customer.installment_balance = bal
        customer.notes = request.POST.get('notes', '').strip()
        customer.save()
        _water_audit(request, 'Updated customer', 'WaterCustomer', customer.account_number, customer.display_name)
        messages.success(request, f'Customer {customer.account_number} updated.')
    except Exception as exc:
        messages.error(request, f'Could not update customer: {exc}')
    return redirect('view_water_customer', customer_id=customer.id)


def _water_create_reading(request):
    customer_id = request.POST.get('customer_id', '').strip()
    reading_date = request.POST.get('reading_date', '').strip()
    billing_period = request.POST.get('billing_period', '').strip()
    current_raw = request.POST.get('current_reading', '').strip()
    if not (customer_id and reading_date and billing_period and current_raw):
        messages.error(request, 'Please complete required meter reading fields.')
        return _water_redirect('readingsBillingTab')
    customer = get_object_or_404(WaterCustomer, pk=customer_id)
    last = customer.readings.order_by('-reading_date', '-created_at').first()
    previous_raw = request.POST.get('previous_reading', '').strip()
    try:
        if previous_raw != '':
            previous = int(previous_raw)
        else:
            previous = int(last.current_reading) if last else 0
        if previous < 0:
            raise ValueError('Previous reading cannot be negative.')
        current = int(current_raw)
        parsed_reading_date = _water_parse_date(reading_date, required=True)
        unpaid = customer.outstanding_balance
        installment = _dec(request.POST.get('installment_balance'), str(customer.installment_balance or 0))
        reading = WaterMeterReading(
            customer=customer,
            reading_date=parsed_reading_date,
            billing_period=billing_period,
            previous_reading=previous,
            current_reading=current,
            previous_bill_unpaid=unpaid,
            installment_balance=installment,
            is_estimated=bool(request.POST.get('is_estimated')),
            reader_name=request.POST.get('reader_name', '').strip(),
            remarks=request.POST.get('remarks', '').strip(),
        )
        reading.save()
        if installment != (customer.installment_balance or Decimal('0')):
            customer.installment_balance = installment
            customer.save(update_fields=['installment_balance', 'updated_at'])
        _water_audit(
            request, 'Recorded meter reading', 'WaterMeterReading', reading.pk,
            f'{customer.account_number} {billing_period} consumption={reading.consumption}',
        )
        messages.success(
            request,
            f'Reading saved for {customer.account_number} '
            f'({reading.consumption} cu.m Â· current â‚±{reading.current_bill} Â· total â‚±{reading.total_bill}). '
            f'Use Generate Bill to create the statement.',
        )
    except Exception as exc:
        messages.error(request, f'Could not save reading: {exc}')
    return _water_redirect('readingsBillingTab')


def _water_bill_from_reading(reading):
    """Create a WaterBill for a reading if one does not already exist. Returns the bill."""
    existing = WaterBill.objects.filter(meter_reading=reading).first()
    if existing:
        return existing, False
    due = reading.reading_date + timedelta(days=15)
    bill = WaterBill(
        bill_number=WaterBill.generate_bill_number(),
        customer=reading.customer,
        meter_reading=reading,
        billing_period=reading.billing_period,
        bill_date=reading.reading_date,
        due_date=due,
        consumption=reading.consumption,
        rate_per_cum=WATER_DEFAULT_RATE,
        previous_bill_unpaid=reading.previous_bill_unpaid or Decimal('0'),
        installment_balance=reading.installment_balance or Decimal('0'),
        fixed_charge=Decimal('0.00'),
        environmental_fee=Decimal('0.00'),
        maintenance_fee=Decimal('0.00'),
    )
    bill.save()
    return bill, True


def _water_generate_bill_from_reading(request):
    reading_id = request.POST.get('reading_id', '').strip()
    reading = get_object_or_404(WaterMeterReading.objects.select_related('customer'), pk=reading_id)
    try:
        bill, created = _water_bill_from_reading(reading)
        if not created:
            messages.info(request, 'A bill already exists for this reading.')
            return _water_redirect('readingsBillingTab')
        _water_audit(
            request, 'Generated bill', 'WaterBill', bill.bill_number,
            f'{reading.customer.account_number} total={bill.total_amount}',
        )
        messages.success(
            request,
            f'Bill {bill.bill_number} generated for {reading.customer.display_name} '
            f'(total â‚±{bill.total_amount}).',
        )
        return redirect('view_water_bill', bill_id=bill.id)
    except Exception as exc:
        messages.error(request, f'Could not generate bill: {exc}')
        return _water_redirect('readingsBillingTab')


def _water_generate_all_bills(request):
    readings = WaterMeterReading.objects.select_related('customer').filter(bill__isnull=True)
    created = 0
    try:
        with transaction.atomic():
            for reading in readings:
                _bill, was_created = _water_bill_from_reading(reading)
                if was_created:
                    created += 1
        if created:
            _water_audit(request, 'Generated all bills', 'WaterBill', '', f'{created} bill(s)')
            messages.success(request, f'Generated {created} bill{"s" if created != 1 else ""}.')
        else:
            messages.info(request, 'No readings left to bill. All readings already have bills.')
    except Exception as exc:
        messages.error(request, f'Could not generate bills: {exc}')
    return _water_redirect('readingsBillingTab')


def _water_create_bill(request):
    return _water_generate_bill_from_reading(request)


@require_dashboard('water_billing_dashboard')
def view_water_bill(request, bill_id):
    bill = get_object_or_404(
        WaterBill.objects.select_related('customer', 'meter_reading'),
        pk=bill_id,
    )
    return render(request, 'water_bill_statement.html', _water_bill_statement_context(bill))


def _water_bill_month_name(billing_period):
    month_name = ''
    if billing_period and len(billing_period) >= 7:
        try:
            period_date = date.fromisoformat(f'{billing_period[:7]}-01')
            month_name = period_date.strftime('%B').upper()
        except ValueError:
            month_name = billing_period
    return month_name


def _water_bill_period_dates(billing_period, end_date):
    start_date = None
    computed_end_date = end_date
    if billing_period and len(billing_period) >= 7:
        try:
            period_start = date.fromisoformat(f'{billing_period[:7]}-01')
            if period_start.month == 1:
                start_date = date(period_start.year - 1, 12, 29)
            else:
                start_date = date(period_start.year, period_start.month - 1, 29)
            computed_end_date = date(period_start.year, period_start.month, 28)
        except ValueError:
            start_date = None
    return start_date, computed_end_date


def _water_format_receipt_date(value):
    if not value:
        return ''
    return value.strftime('%B %d, %Y').upper()


def _water_bill_statement_context(bill, is_preview=False):
    billing_end_date = getattr(bill.meter_reading, 'reading_date', None) or getattr(bill, 'bill_date', None)
    billing_start_date, billing_end_date = _water_bill_period_dates(bill.billing_period, billing_end_date)
    return {
        'bill': bill,
        'reading': bill.meter_reading,
        'customer': bill.customer,
        'month_name': _water_bill_month_name(bill.billing_period),
        'billing_start_date': billing_start_date,
        'billing_end_date': billing_end_date,
        'billing_start_label': _water_format_receipt_date(billing_start_date),
        'billing_end_label': _water_format_receipt_date(billing_end_date),
        'location_header': 'Purok Batong, Nanyo, Panabo City',
        'is_preview': is_preview,
    }


@require_dashboard('water_billing_dashboard')
def print_water_bills_batch(request):
    raw_ids = request.GET.getlist('bill_ids')
    if not raw_ids and request.GET.get('ids'):
        raw_ids = [part.strip() for part in request.GET.get('ids', '').split(',') if part.strip()]

    bill_ids = []
    seen = set()
    for raw in raw_ids:
        try:
            pk = int(raw)
        except (TypeError, ValueError):
            continue
        if pk in seen:
            continue
        seen.add(pk)
        bill_ids.append(pk)

    if not bill_ids:
        messages.error(request, 'Select at least one bill to print.')
        return redirect(f"{reverse('water_billing_dashboard')}?tab=readingsBillingTab")

    truncated = False
    if len(bill_ids) > 6:
        bill_ids = bill_ids[:6]
        truncated = True
        messages.warning(request, 'Only the first 6 selected bills are printed on one long bond page.')

    bills = list(
        WaterBill.objects.select_related('customer', 'meter_reading')
        .filter(pk__in=bill_ids)
        .exclude(status='cancelled')
    )
    bill_by_id = {b.id: b for b in bills}
    ordered_bills = [bill_by_id[pk] for pk in bill_ids if pk in bill_by_id]

    if not ordered_bills:
        messages.error(request, 'No printable bills found for the selected IDs.')
        return redirect(f"{reverse('water_billing_dashboard')}?tab=readingsBillingTab")

    receipt_items = [_water_bill_statement_context(bill) for bill in ordered_bills]
    return render(request, 'water_bills_batch_print.html', {
        'receipt_items': receipt_items,
        'bill_count': len(receipt_items),
        'truncated': truncated,
    })


@require_dashboard('water_billing_dashboard')
def view_water_customer(request, customer_id):
    customer = get_object_or_404(WaterCustomer.objects.select_related('zone'), pk=customer_id)
    if request.method == 'POST' and request.POST.get('action') == 'update_customer':
        return _water_update_customer(request, customer)

    readings = customer.readings.select_related('bill').all()
    bills = customer.bills.select_related('meter_reading').all()
    payments = customer.payments.select_related('bill').all()
    service_actions = customer.service_actions.all()

    billed_total = Decimal('0.00')
    paid_total = Decimal('0.00')
    for bill in bills.exclude(status='cancelled'):
        billed_total += bill.total_amount
        paid_total += bill.amount_paid or Decimal('0.00')

    return render(request, 'water_customer_detail.html', {
        'customer': customer,
        'readings': readings,
        'bills': bills,
        'payments': payments,
        'service_actions': service_actions,
        'outstanding_balance': customer.outstanding_balance,
        'billed_total': billed_total,
        'paid_total': paid_total,
        'reading_count': readings.count() if hasattr(readings, 'count') else len(readings),
        'bill_count': bills.count() if hasattr(bills, 'count') else len(bills),
        'payment_count': payments.count() if hasattr(payments, 'count') else len(payments),
        'customer_types': WATER_CUSTOMER_TYPES,
        'connection_statuses': WATER_CONNECTION_STATUS,
        'water_zones': WaterZone.objects.order_by('name'),
    })


@require_dashboard('water_billing_dashboard')
def view_water_reading_preview(request, reading_id):
    """Preview statement from a reading before/without a generated bill."""
    reading = get_object_or_404(
        WaterMeterReading.objects.select_related('customer'),
        pk=reading_id,
    )
    existing_bill = WaterBill.objects.filter(meter_reading=reading).first()
    if existing_bill:
        return redirect('view_water_bill', bill_id=existing_bill.id)
    customer = reading.customer
    month_name = ''
    if reading.billing_period and len(reading.billing_period) >= 7:
        try:
            period_date = date.fromisoformat(f'{reading.billing_period[:7]}-01')
            month_name = period_date.strftime('%B').upper()
        except ValueError:
            month_name = reading.billing_period
    preview = type('BillPreview', (), {
        'bill_number': '(Preview)',
        'billing_period': reading.billing_period,
        'bill_date': reading.reading_date,
        'due_date': reading.reading_date + timedelta(days=15),
        'consumption': reading.consumption,
        'consumption_charge': reading.current_bill,
        'current_bill': reading.current_bill,
        'previous_bill_unpaid': reading.previous_bill_unpaid,
        'installment_balance': reading.installment_balance,
        'total_amount': reading.total_bill,
        'status': 'draft',
    })()
    billing_start_date, billing_end_date = _water_bill_period_dates(reading.billing_period, reading.reading_date)
    return render(request, 'water_bill_statement.html', {
        'bill': preview,
        'reading': reading,
        'customer': customer,
        'month_name': month_name,
        'billing_start_date': billing_start_date,
        'billing_end_date': billing_end_date,
        'billing_start_label': _water_format_receipt_date(billing_start_date),
        'billing_end_label': _water_format_receipt_date(billing_end_date),
        'location_header': 'Purok Batong, Nanyo, Panabo City',
        'is_preview': True,
    })

def _water_create_payment(request):
    bill_id = request.POST.get('bill_id', '').strip()
    payment_date = request.POST.get('payment_date', '').strip()
    amount = _dec(request.POST.get('amount'))
    if not (bill_id and payment_date and amount > 0):
        messages.error(request, 'Please complete required payment fields.')
        return _water_redirect('paymentsTab')
    try:
        parsed_payment_date = _water_parse_date(payment_date, required=True)
    except ValueError:
        messages.error(request, 'Please enter a valid payment date.')
        return _water_redirect('paymentsTab')
    bill = get_object_or_404(WaterBill, pk=bill_id)
    if bill.status == 'cancelled':
        messages.error(request, 'Cannot pay a cancelled bill.')
        return _water_redirect('paymentsTab')
    payment_method = request.POST.get('payment_method', 'cash').strip()
    allowed_methods = {value for value, _label in WATER_PAYMENT_METHODS}
    if payment_method not in allowed_methods:
        messages.error(request, 'Payment method must be Cash or GCash.')
        return _water_redirect('paymentsTab')
    try:
        with transaction.atomic():
            payment = WaterPayment.objects.create(
                receipt_number=request.POST.get('receipt_number', '').strip() or WaterPayment.generate_receipt_number(),
                bill=bill,
                customer=bill.customer,
                payment_date=parsed_payment_date,
                amount=amount,
                payment_method=payment_method,
                reference_number=request.POST.get('reference_number', '').strip(),
                received_by=request.POST.get('received_by', '').strip(),
                remarks=request.POST.get('remarks', '').strip(),
            )
            bill.amount_paid = (bill.amount_paid or Decimal('0')) + amount
            bill.refresh_status()
            bill.save(update_fields=['amount_paid', 'status', 'updated_at'])
            _water_audit(
                request, 'Recorded payment', 'WaterPayment', payment.receipt_number,
                f'{bill.bill_number} amount={amount} method={payment.payment_method}',
            )
        messages.success(request, f'Payment {payment.receipt_number} recorded.')
    except Exception as exc:
        messages.error(request, f'Could not record payment: {exc}')
    return _water_redirect('paymentsTab')


def _water_get_edit_contract(request):
    contract_id = request.GET.get('contract_id', '').strip()
    if not contract_id.isdigit():
        return None
    return WaterServiceContract.objects.filter(pk=contract_id).select_related('customer').first()


def _water_contract_classification_from_customer(customer):
    mapping = {
        'residential': 'residential',
        'government': 'government',
        'commercial': 'commercial',
        'industrial': 'commercial',
    }
    return mapping.get(customer.customer_type, 'residential')


def _water_contract_defaults(customer, application_status):
    if not customer or application_status == 'new':
        return {}
    zone = customer.zone.name if customer.zone_id else ''
    address = customer.service_address or ''
    contract_address = address
    if zone and zone not in address:
        contract_address = f'{zone}, {address}'.strip(', ')
    return {
        'last_name': customer.last_name,
        'first_name': customer.first_name,
        'zone_purok': zone,
        'connection_location': address,
        'contract_address': contract_address,
        'contact_number': customer.contact_number,
        'meter_size': customer.meter_number,
        'customer_classification': _water_contract_classification_from_customer(customer),
        'ack_payee_name': customer.display_name,
    }


def _water_contract_from_post(request):
    application_status = request.POST.get('application_status', 'new').strip() or 'new'
    if application_status not in dict(WATER_CONTRACT_APPLICATION_STATUS):
        application_status = 'new'
    customer = None
    customer_id = request.POST.get('contract_customer_id', '').strip()
    if customer_id.isdigit():
        customer = WaterCustomer.objects.filter(pk=customer_id).first()

    home_ownership = request.POST.get('home_ownership', '').strip()
    if home_ownership not in dict(WATER_CONTRACT_HOME_OWNERSHIP):
        home_ownership = ''
    customer_classification = request.POST.get('customer_classification', '').strip()
    if customer_classification not in dict(WATER_CONTRACT_CLASSIFICATION):
        customer_classification = ''
    civil_status = request.POST.get('civil_status', '').strip()
    if civil_status not in dict(WATER_CONTRACT_CIVIL_STATUS):
        civil_status = ''

    def _int_field(name):
        raw = request.POST.get(name, '').strip()
        if not raw.isdigit():
            return None
        return int(raw)

    return {
        'customer': customer,
        'application_status': application_status,
        'last_name': request.POST.get('last_name', '').strip(),
        'first_name': request.POST.get('first_name', '').strip(),
        'middle_name': request.POST.get('middle_name', '').strip(),
        'zone_purok': request.POST.get('zone_purok', '').strip(),
        'barangay': request.POST.get('barangay', '').strip(),
        'municipality_city': request.POST.get('municipality_city', '').strip(),
        'contact_number': request.POST.get('contact_number', '').strip(),
        'spouse_last_name': request.POST.get('spouse_last_name', '').strip(),
        'spouse_first_name': request.POST.get('spouse_first_name', '').strip(),
        'spouse_middle_name': request.POST.get('spouse_middle_name', '').strip(),
        'home_ownership': home_ownership,
        'customer_classification': customer_classification,
        'original_registered_name': request.POST.get('original_registered_name', '').strip(),
        'meter_size': request.POST.get('meter_size', '').strip(),
        'connection_location': request.POST.get('connection_location', '').strip(),
        'near_beside': request.POST.get('near_beside', '').strip(),
        'ack_payee_name': request.POST.get('ack_payee_name', '').strip(),
        'ack_amount': _dec(request.POST.get('ack_amount'), '0'),
        'ack_received_by': request.POST.get('ack_received_by', '').strip(),
        'ack_date': _water_parse_date(request.POST.get('ack_date')),
        'contract_date': _water_parse_date(request.POST.get('contract_date')),
        'civil_status': civil_status,
        'contract_spouse_name': request.POST.get('contract_spouse_name', '').strip(),
        'contract_address': request.POST.get('contract_address', '').strip(),
        'signed_day': _int_field('signed_day'),
        'signed_month': request.POST.get('signed_month', '').strip(),
        'signed_year': _int_field('signed_year'),
        'notary_province': request.POST.get('notary_province', '').strip(),
        'notary_city': request.POST.get('notary_city', '').strip(),
        'notary_day': _int_field('notary_day'),
        'notary_month': request.POST.get('notary_month', '').strip(),
        'notary_year': _int_field('notary_year'),
        'notary_location': request.POST.get('notary_location', '').strip(),
        'notary_witness1_name': request.POST.get('notary_witness1_name', '').strip(),
        'notary_witness1_id': request.POST.get('notary_witness1_id', '').strip(),
        'notary_witness1_id_issued': request.POST.get('notary_witness1_id_issued', '').strip(),
        'notary_witness1_id_at': request.POST.get('notary_witness1_id_at', '').strip(),
        'notary_witness2_name': request.POST.get('notary_witness2_name', '').strip(),
        'notary_witness2_id': request.POST.get('notary_witness2_id', '').strip(),
        'notary_witness2_id_issued': request.POST.get('notary_witness2_id_issued', '').strip(),
        'notary_witness2_id_at': request.POST.get('notary_witness2_id_at', '').strip(),
        'notary_doc_no': request.POST.get('notary_doc_no', '').strip(),
        'notary_page_no': request.POST.get('notary_page_no', '').strip(),
        'notary_book_no': request.POST.get('notary_book_no', '').strip(),
        'notary_series_year': request.POST.get('notary_series_year', '').strip(),
    }


def _water_apply_contract_fields(contract, data):
    for key, value in data.items():
        setattr(contract, key, value)


def _water_create_service_contract(request):
    data = _water_contract_from_post(request)
    if not (data['last_name'] and data['first_name']):
        messages.error(request, 'Applicant last name and first name are required.')
        return _water_redirect('disconnectTab')
    contract = WaterServiceContract()
    _water_apply_contract_fields(contract, data)
    contract.save()
    _water_audit(request, 'Saved service contract', 'WaterServiceContract', contract.pk, contract.applicant_display_name)
    messages.success(request, f'Service contract saved for {contract.applicant_display_name}.')
    return redirect(f"{reverse('water_billing_dashboard')}?tab=disconnectTab&contract_id={contract.pk}")


def _water_update_service_contract(request):
    contract_id = request.POST.get('contract_id', '').strip()
    contract = get_object_or_404(WaterServiceContract, pk=contract_id)
    data = _water_contract_from_post(request)
    if not (data['last_name'] and data['first_name']):
        messages.error(request, 'Applicant last name and first name are required.')
        return redirect(f"{reverse('water_billing_dashboard')}?tab=disconnectTab&contract_id={contract.pk}")
    _water_apply_contract_fields(contract, data)
    contract.save()
    _water_audit(request, 'Updated service contract', 'WaterServiceContract', contract.pk, contract.applicant_display_name)
    messages.success(request, f'Service contract updated for {contract.applicant_display_name}.')
    return redirect(f"{reverse('water_billing_dashboard')}?tab=disconnectTab&contract_id={contract.pk}")


def _water_service_contract_context(contract):
    def fmt_date(value):
        return value.strftime('%B %d, %Y') if value else ''

    def fmt_peso(value):
        return f'{Decimal(value or 0):,.2f}'

    def blank(value):
        text = str(value or '').strip()
        return text if text else '________________'

    civil = contract.civil_status or ''
    if civil == 'married' and contract.contract_spouse_name:
        civil_text = f'married to {contract.contract_spouse_name}'
    elif civil == 'single':
        civil_text = 'single'
    else:
        civil_text = 'single/married to ________________'

    return {
        'contract': contract,
        'blank': blank,
        'fmt_date': fmt_date,
        'fmt_peso': fmt_peso,
        'installation_fee_residential': fmt_peso(WATER_INSTALLATION_FEE),
        'installation_fee_commercial': fmt_peso(WATER_INSTALLATION_FEE),
        'contract_date_display': fmt_date(contract.contract_date) or '________________',
        'ack_date_display': fmt_date(contract.ack_date) or '________________',
        'ack_amount_display': fmt_peso(contract.ack_amount) if contract.ack_amount else '',
        'civil_text': civil_text,
        'signed_day': contract.signed_day or '______',
        'signed_month': contract.signed_month or '________________',
        'signed_year': contract.signed_year or '____',
    }


@require_dashboard('water_billing_dashboard')
def view_water_service_contract(request, contract_id):
    contract = get_object_or_404(WaterServiceContract.objects.select_related('customer'), pk=contract_id)
    ctx = _water_service_contract_context(contract)
    ctx['back_url'] = f"{reverse('water_billing_dashboard')}?tab=disconnectTab&contract_id={contract.pk}"
    return render(request, 'water_service_contract_print.html', ctx)


def _water_create_service_action(request):
    customer_id = request.POST.get('customer_id', '').strip()
    action_type = request.POST.get('action_type', '').strip()
    action_date = request.POST.get('action_date', '').strip()
    if not (customer_id and action_type and action_date):
        messages.error(request, 'Please complete required disconnection/reconnection fields.')
        return _water_redirect('disconnectTab')
    try:
        parsed_action_date = _water_parse_date(action_date, required=True)
    except ValueError:
        messages.error(request, 'Please enter a valid action date.')
        return _water_redirect('disconnectTab')
    customer = get_object_or_404(WaterCustomer, pk=customer_id)
    status = request.POST.get('status', 'for_disconnection').strip() or 'for_disconnection'
    if status not in dict(WATER_SERVICE_ACTION_STATUS):
        status = 'for_disconnection'
    try:
        action = WaterServiceAction.objects.create(
            customer=customer,
            action_type=action_type,
            action_date=parsed_action_date,
            status=status,
            reason=request.POST.get('reason', '').strip(),
            reconnection_fee=_dec(request.POST.get('reconnection_fee'), str(WATER_DEFAULT_RECONNECT_FEE)),
            fee_paid=bool(request.POST.get('fee_paid')),
            performed_by=request.POST.get('performed_by', '').strip(),
            notes=request.POST.get('notes', '').strip(),
        )
        _apply_service_status(customer, action_type, status)
        _water_audit(request, f'Recorded {action_type}', 'WaterServiceAction', action.pk, customer.account_number)
        messages.success(request, f'{action.get_action_type_display()} recorded for {customer.account_number}.')
    except Exception as exc:
        messages.error(request, f'Could not save service action: {exc}')
    return _water_redirect('disconnectTab')


def _apply_service_status(customer, action_type, status):
    if action_type == 'disconnection':
        if status == 'disconnected':
            customer.connection_status = 'disconnected'
        else:
            customer.connection_status = 'for_disconnection'
    elif action_type == 'reconnection':
        # Finalized reconnection restores active service.
        if status == 'disconnected':
            customer.connection_status = 'active'
        else:
            return
    customer.save(update_fields=['connection_status', 'updated_at'])


def _water_complete_service_action(request):
    action_id = request.POST.get('action_id', '').strip()
    action = get_object_or_404(WaterServiceAction, pk=action_id)
    action.status = 'disconnected'
    if request.POST.get('fee_paid'):
        action.fee_paid = True
    action.save(update_fields=['status', 'fee_paid'])
    _apply_service_status(action.customer, action.action_type, action.status)
    _water_audit(request, f'Finalized {action.action_type}', 'WaterServiceAction', action.pk, action.customer.account_number)
    if action.action_type == 'reconnection':
        messages.success(request, f'Reconnection finalized for {action.customer.account_number}.')
    else:
        messages.success(request, f'{action.customer.account_number} marked disconnected.')
    return _water_redirect('disconnectTab')


def _water_delete_customer(request):
    customer = get_object_or_404(WaterCustomer, pk=request.POST.get('customer_id'))
    label = customer.account_number
    customer.delete()
    _water_audit(request, 'Deleted customer', 'WaterCustomer', label)
    messages.success(request, f'Customer {label} deleted.')
    return _water_redirect('customersTab')


def _water_delete_reading(request):
    reading = get_object_or_404(WaterMeterReading, pk=request.POST.get('reading_id'))
    bill = WaterBill.objects.filter(meter_reading=reading).first()
    if bill and bill.payments.exists():
        messages.error(request, 'Cannot delete a reading whose bill already has payments.')
        return _water_redirect('readingsBillingTab')
    pk = reading.pk
    bill_label = bill.bill_number if bill else ''
    with transaction.atomic():
        if bill:
            bill.delete()
        reading.delete()
    _water_audit(request, 'Deleted reading & bill', 'WaterMeterReading', pk, bill_label)
    messages.success(request, 'Meter reading and related bill deleted.')
    return _water_redirect('readingsBillingTab')


def _water_delete_bill(request):
    bill = get_object_or_404(WaterBill, pk=request.POST.get('bill_id'))
    if bill.payments.exists():
        messages.error(request, 'Cannot delete a bill with payments. Cancel it instead or delete payments first.')
        return _water_redirect('readingsBillingTab')
    label = bill.bill_number
    bill.delete()
    _water_audit(request, 'Deleted bill', 'WaterBill', label)
    messages.success(request, f'Bill {label} deleted.')
    return _water_redirect('readingsBillingTab')


def _water_delete_payment(request):
    payment = get_object_or_404(WaterPayment, pk=request.POST.get('payment_id'))
    bill = payment.bill
    amount = payment.amount
    label = payment.receipt_number
    with transaction.atomic():
        payment.delete()
        bill.amount_paid = max((bill.amount_paid or Decimal('0')) - amount, Decimal('0'))
        bill.refresh_status()
        bill.save(update_fields=['amount_paid', 'status', 'updated_at'])
    _water_audit(request, 'Deleted payment', 'WaterPayment', label)
    messages.success(request, f'Payment {label} deleted.')
    return _water_redirect('paymentsTab')


@require_dashboard('water_billing_dashboard')
def water_billing_export_csv(request):
    report_type = request.GET.get('report', 'billing')
    rows = _water_report_rows(report_type)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="water_{report_type}_report.csv"'
    writer = csv.writer(response)

    if report_type in ('collection', 'daily_collection', 'revenue'):
        writer.writerow(['Receipt #', 'Date', 'Account', 'Customer', 'Bill #', 'Amount', 'Method'])
        for p in rows:
            writer.writerow([
                p.receipt_number, p.payment_date, p.customer.account_number, p.customer.display_name,
                p.bill.bill_number, p.amount, p.get_payment_method_display(),
            ])
    elif report_type == 'outstanding':
        writer.writerow(['Bill #', 'Account', 'Customer', 'Due Date', 'Total', 'Paid', 'Balance', 'Status'])
        for b in rows:
            writer.writerow([
                b.bill_number, b.customer.account_number, b.customer.display_name, b.due_date,
                b.total_amount, b.amount_paid, b.balance_due, b.status,
            ])
    elif report_type in ('consumption', 'readings'):
        writer.writerow(['Account', 'Customer', 'Period', 'Previous', 'Current', 'Consumption', 'Estimated', 'Date'])
        for r in rows:
            writer.writerow([
                r.customer.account_number, r.customer.display_name, r.billing_period,
                r.previous_reading, r.current_reading, r.consumption,
                'Yes' if r.is_estimated else 'No', r.reading_date,
            ])
    elif report_type == 'customers':
        writer.writerow(['Account', 'Name', 'Type', 'Meter', 'Status', 'Address', 'Contact', 'Registered'])
        for c in rows:
            writer.writerow([
                c.account_number, c.display_name, c.get_customer_type_display(), c.meter_number,
                c.get_connection_status_display(), c.service_address, c.contact_number, c.registration_date,
            ])
    elif report_type in ('disconnection', 'reconnection'):
        writer.writerow(['Type', 'Account', 'Customer', 'Date', 'Status', 'Reason', 'Fee', 'Fee Paid'])
        for a in rows:
            writer.writerow([
                a.get_action_type_display(), a.customer.account_number, a.customer.display_name,
                a.action_date, a.status, a.reason, a.reconnection_fee, 'Yes' if a.fee_paid else 'No',
            ])
    else:
        writer.writerow(['Bill #', 'Account', 'Customer', 'Period', 'Consumption', 'Total', 'Paid', 'Status', 'Bill Date'])
        for b in rows:
            writer.writerow([
                b.bill_number, b.customer.account_number, b.customer.display_name, b.billing_period,
                b.consumption, b.total_amount, b.amount_paid, b.status, b.bill_date,
            ])
    _water_audit(request, 'Exported report', 'Report', report_type, f'rows={len(rows)}')
    return response
