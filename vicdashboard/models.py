from datetime import date
from decimal import Decimal

from django.db import models


PAYMENT_METHODS = [
    ('cash', 'Cash'),
    ('gcash', 'G-Cash'),
    ('credit_card', 'Credit Card'),
    ('bank_transfer', 'Bank Transfer'),
    ('account_receivable', 'Account Receivable'),
]


class InventoryItem(models.Model):
    product_code = models.CharField(max_length=50, blank=True, default='')
    name = models.CharField(max_length=200)
    picture = models.ImageField(upload_to='inventory_pics/', blank=True, null=True)
    size = models.CharField(max_length=100, blank=True, default='')
    stock_available = models.PositiveIntegerField(default=0)
    pcs_per_ctn = models.PositiveIntegerField(default=0)
    carton_size = models.CharField(max_length=100, blank=True, default='')
    net_weight = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gross_weight = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name or self.product_code or 'Inventory Item'


class SalesOrder(models.Model):
    customer_name = models.CharField(max_length=200)
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='sales_orders')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refund_quantity = models.PositiveIntegerField(default=0)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refund_status = models.CharField(max_length=20, default='none')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    customer_contact = models.CharField(max_length=100, blank=True, default='')
    invoice_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHODS, default='cash')

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        super().save(*args, **kwargs)

    def generate_invoice_number(self):
        import secrets
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d')

        while True:
            random_part = secrets.token_hex(3).upper()
            candidate = f"INV-{timestamp}-{random_part}"
            if not SalesOrder.objects.filter(invoice_number=candidate).exists():
                return candidate
    
    @property
    def remaining_quantity(self):
        return max(self.quantity - self.refund_quantity, 0)

    def __str__(self):
        return f'{self.customer_name} - {self.inventory_item}'


class Quotation(models.Model):
    quotation_number = models.CharField(max_length=100)
    quotation_date = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=10, default='PHP')
    currency_other = models.CharField(max_length=20, blank=True, default='')
    customer_company = models.CharField(max_length=200, blank=True, default='')
    customer_contact = models.CharField(max_length=200, blank=True, default='')
    customer_address = models.TextField(blank=True, default='')
    customer_email = models.EmailField(blank=True, default='')
    customer_phone = models.CharField(max_length=50, blank=True, default='')
    subject = models.CharField(max_length=255, blank=True, default='')
    payment_terms = models.CharField(max_length=255, blank=True, default='')
    delivery_terms = models.CharField(max_length=255, blank=True, default='')
    warranty = models.CharField(max_length=255, blank=True, default='')
    other_terms = models.TextField(blank=True, default='')
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    shipping = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    initial_payment = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    prepared_name = models.CharField(max_length=200, blank=True, default='')
    prepared_title = models.CharField(max_length=200, blank=True, default='')
    prepared_signature = models.TextField(blank=True, default='')
    prepared_date = models.DateField(null=True, blank=True)
    approved_signature = models.TextField(blank=True, default='')
    approved_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.quotation_number or f'Product Quotation {self.pk}'

    @classmethod
    def generate_quotation_number(cls):
        from datetime import date
        return _next_sequential_number(cls, 'quotation_number', f'PQ-{date.today().year}-')

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            self.quotation_number = self.generate_quotation_number()
        super().save(*args, **kwargs)

    @property
    def payment_status(self):
        if self.grand_total and self.balance_due <= 0:
            return 'Paid'
        if self.initial_payment and self.initial_payment > 0:
            return 'Partial'
        return 'Pending'


class QuotationLine(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='lines')
    item_number = models.PositiveIntegerField(default=0)
    product_description = models.TextField(blank=True, default='')
    quantity = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=50, blank=True, default='')
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ['item_number']

    def __str__(self):
        return f'{self.quotation} line {self.item_number}'


class ServiceQuotation(models.Model):
    quotation_number = models.CharField(max_length=100)
    quotation_date = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=10, default='PHP')
    currency_other = models.CharField(max_length=20, blank=True, default='')
    customer_company = models.CharField(max_length=200, blank=True, default='')
    customer_contact = models.CharField(max_length=200, blank=True, default='')
    customer_address = models.TextField(blank=True, default='')
    customer_email = models.EmailField(blank=True, default='')
    customer_phone = models.CharField(max_length=50, blank=True, default='')
    payment_terms = models.CharField(max_length=255, blank=True, default='')
    service_schedule = models.CharField(max_length=255, blank=True, default='')
    warranty = models.CharField(max_length=255, blank=True, default='')
    other_terms = models.TextField(blank=True, default='')
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    other_fees = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    initial_payment = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    prepared_name = models.CharField(max_length=200, blank=True, default='')
    prepared_title = models.CharField(max_length=200, blank=True, default='')
    prepared_signature = models.TextField(blank=True, default='')
    prepared_date = models.DateField(null=True, blank=True)
    approved_signature = models.TextField(blank=True, default='')
    approved_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.quotation_number or f'Service Quotation {self.pk}'

    @classmethod
    def generate_quotation_number(cls):
        from datetime import date
        return _next_sequential_number(cls, 'quotation_number', f'SQ-{date.today().year}-')

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            self.quotation_number = self.generate_quotation_number()
        super().save(*args, **kwargs)

    @property
    def payment_status(self):
        if self.grand_total and self.balance_due <= 0:
            return 'Paid'
        if self.initial_payment and self.initial_payment > 0:
            return 'Partial'
        return 'Pending'


class ServiceQuotationLine(models.Model):
    service_quotation = models.ForeignKey(ServiceQuotation, on_delete=models.CASCADE, related_name='lines')
    item_number = models.PositiveIntegerField(default=0)
    service_description = models.TextField(blank=True, default='')
    quantity = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=50, blank=True, default='')
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ['item_number']

    def __str__(self):
        return f'{self.service_quotation} line {self.item_number}'


class HRDocument(models.Model):
    DOCUMENT_TYPES = [
        ('contract', 'Contract'),
        ('legal', 'Legal'),
        ('personnel', 'Personnel'),
        ('policy', 'Policy'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='hr_documents/')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='other')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    # Optional: link to an employee (if you add Employee model later)
    # employee = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title


# ========== PAYROLL MODELS ==========

class Department(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Position(models.Model):
    title = models.CharField(max_length=100)
    pay_grade = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)

    def __str__(self):
        return self.title


class Employee(models.Model):
    FREQUENCY_CHOICES = [
        ('monthly', 'Monthly'),
        ('semi-monthly', 'Semi-monthly'),
    ]
    user = models.OneToOneField(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employee_profile'
    )
    employee_id = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    birth_date = models.DateField()
    hire_date = models.DateField()
    termination_date = models.DateField(null=True, blank=True)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2)
    salary_frequency = models.CharField(max_length=15, choices=FREQUENCY_CHOICES, default='monthly')
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    position = models.ForeignKey(Position, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.employee_id})'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @classmethod
    def generate_employee_id(cls):
        prefix = 'EMP-'
        max_num = 0
        for employee_id in cls.objects.filter(employee_id__startswith=prefix).values_list('employee_id', flat=True):
            suffix = employee_id[len(prefix):]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))
        return f'{prefix}{max_num + 1:03d}'

    def save(self, *args, **kwargs):
        if not self.employee_id:
            self.employee_id = self.generate_employee_id()
        super().save(*args, **kwargs)


class PayPeriod(models.Model):
    PERIOD_TYPES = [('monthly', 'Monthly'), ('semi-monthly', 'Semi-monthly')]
    start_date = models.DateField()
    end_date = models.DateField()
    pay_date = models.DateField()
    period_type = models.CharField(max_length=15, choices=PERIOD_TYPES, default='monthly')
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.start_date} – {self.end_date} ({self.period_type})'


class PayrollRun(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('computed', 'Computed'),
        ('approved', 'Approved'),
        ('disbursed', 'Disbursed'),
    ]
    pay_period = models.ForeignKey(PayPeriod, on_delete=models.PROTECT)
    cutoff_start = models.DateField()
    cutoff_end = models.DateField()
    processing_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Payroll {self.id} – {self.cutoff_start} to {self.cutoff_end}'


class PayrollLine(models.Model):
    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name='lines')
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    gross_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    breakdown = models.JSONField(default=dict, blank=True)  # store detailed components
    regular_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    holiday_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['employee__last_name']

    def __str__(self):
        return f'{self.employee} – {self.payroll_run}'


class DeductionConfig(models.Model):
    TYPE_CHOICES = [
        ('statutory', 'Statutory'),
        ('loan', 'Loan'),
        ('voluntary', 'Voluntary'),
    ]
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='voluntary')
    fixed_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    percentage_of_gross = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    effective_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f'{self.code} – {self.name}'


class EmployeeDeduction(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='deductions')
    deduction_config = models.ForeignKey(DeductionConfig, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    total_remaining = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    frequency = models.CharField(max_length=20, default='per_payroll')

    class Meta:
        ordering = ['employee', 'start_date']

    def __str__(self):
        return f'{self.employee} – {self.deduction_config.name}'


class TaxBracket(models.Model):
    TAX_TYPES = [
        ('withholding', 'Withholding Tax'),
        ('sss', 'SSS'),
        ('philhealth', 'PhilHealth'),
        ('pagibig', 'Pag-IBIG'),
    ]
    effective_date = models.DateField()
    min_amount = models.DecimalField(max_digits=12, decimal_places=2)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    base_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # e.g., 0.15 for 15%
    tax_type = models.CharField(max_length=20, choices=TAX_TYPES, default='withholding')

    class Meta:
        ordering = ['tax_type', 'effective_date', 'min_amount']

    def __str__(self):
        return f'{self.tax_type} – {self.effective_date}'


# ========== TIME & ATTENDANCE MODELS ==========

class AttendanceLog(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('leave', 'On Leave'),
        ('holiday', 'Holiday'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_logs')
    date = models.DateField()
    clock_in = models.TimeField(null=True, blank=True)
    clock_out = models.TimeField(null=True, blank=True)
    break_start = models.TimeField(null=True, blank=True)
    break_end = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    remarks = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        unique_together = ['employee', 'date']  # one log per employee per day

    def __str__(self):
        return f'{self.employee} – {self.date}'

    @property
    def hours_worked(self):
        if not self.clock_in or not self.clock_out:
            return None
        from datetime import datetime as _datetime
        start = _datetime.combine(self.date, self.clock_in)
        end = _datetime.combine(self.date, self.clock_out)
        if end < start:
            return None
        seconds = (end - start).total_seconds()
        if self.break_start and self.break_end:
            b_start = _datetime.combine(self.date, self.break_start)
            b_end = _datetime.combine(self.date, self.break_end)
            if b_end > b_start:
                seconds -= (b_end - b_start).total_seconds()
        return round(max(seconds, 0) / 3600, 2)

    def __str__(self):
        return f'{self.employee} – {self.date}'


class ShiftSchedule(models.Model):
    SCHEDULE_TYPES = [
        ('regular', 'Regular'),
        ('flexi', 'Flexi'),
        ('compressed', 'Compressed'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='shift_schedules')
    effective_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPES, default='regular')

    class Meta:
        ordering = ['effective_date']

    def __str__(self):
        return f'{self.employee} – {self.effective_date} to {self.end_date or "now"}'


class LeaveBalance(models.Model):
    LEAVE_TYPES = [
        ('vacation', 'Vacation Leave'),
        ('sick', 'Sick Leave'),
        ('emergency', 'Emergency Leave'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    balance_credits = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    used_credits = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    as_of_date = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ['employee', 'leave_type']

    def __str__(self):
        return f'{self.employee} – {self.leave_type} ({self.balance_credits} credits)'


class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    start_date = models.DateField()
    end_date = models.DateField()
    leave_type = models.CharField(max_length=20, choices=LeaveBalance.LEAVE_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    days_requested = models.DecimalField(max_digits=5, decimal_places=2)
    submitted_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.employee} – {self.leave_type} ({self.status})'


class Holiday(models.Model):
    HOLIDAY_TYPES = [
        ('regular', 'Regular Holiday'),
        ('special', 'Special Non-Working Holiday'),
    ]
    date = models.DateField(unique=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=HOLIDAY_TYPES)

    def __str__(self):
        return f'{self.date} – {self.name}'


class RefundRecord(models.Model):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='refunds')
    refund_quantity = models.PositiveIntegerField()
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2)
    refund_date = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)
    processed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='process_refunds')

    class Meta:
        ordering = ['-refund_date']

    def __str__(self):
        return f'Refund for {self.sales_order} - {self.refund_quantity} pcs'

class Delivery(models.Model):
    delivery_date = models.DateField()
    driver = models.CharField(max_length = 100)
    delivered_from = models.CharField(max_length = 200)
    delivered_to = models.CharField(max_length = 200)
    delivery_number = models.CharField(max_length=50, unique=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.delivery_number:
            self.delivery_number = self.generate_delivery_number()
        super().save(*args, **kwargs)

    def generate_delivery_number(self):
        import secrets
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d')
        while True:
            random_part = secrets.token_hex(3).upper()
            candidate = f"DLV-{timestamp}-{random_part}"
            if not Delivery.objects.filter(delivery_number=candidate).exists():
                return candidate
            
    @property
    def total_cost(self):
        return sum(line.total_cost for line in self.lines.all())
    
    def __str__(self):
        return f"Delivery {self.delivery_number} - {self.delivery_date}"

class DeliveryLine(models.Model):
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name="lines")
    item_type = models.CharField(max_length=200)
    quantity_cartons = models.PositiveIntegerField()
    pcs_per_carton = models.PositiveIntegerField()
    cost_per_carton = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def total_pcs(self):
        return self.quantity_cartons * self.pcs_per_carton

    @property
    def total_cost(self):
        return self.quantity_cartons * self.pcs_per_carton  * self.cost_per_carton

    def __str__(self):
        return f"{self.item_type} - {self.quantity_cartons} ctn"


# ========== SERVICES MODELS ==========

def _next_sequential_number(model, field_name, prefix):
    """Return the next unique number like PREFIX-001 for the given model field."""
    max_num = 0
    for value in model.objects.filter(**{f'{field_name}__startswith': prefix}).values_list(field_name, flat=True):
        suffix = value[len(prefix):]
        if suffix.isdigit():
            max_num = max(max_num, int(suffix))
    return f'{prefix}{max_num + 1:03d}'


class ServiceRepairReport(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('released', 'Released'),
    ]

    report_number = models.CharField(max_length=50, unique=True)
    report_date = models.DateField()
    customer_name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True, default='')
    contact_number = models.CharField(max_length=100, blank=True, default='')
    customer_address = models.TextField(blank=True, default='')
    equipment = models.CharField(max_length=200)
    model_number = models.CharField(max_length=100, blank=True, default='')
    serial_number = models.CharField(max_length=100, blank=True, default='')
    complaint = models.TextField()
    diagnosis = models.TextField(blank=True, default='')
    repairs_performed = models.TextField(blank=True, default='')
    parts_used = models.TextField(blank=True, default='')
    technician = models.CharField(max_length=200, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    recommendations = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-report_date', '-created_at']

    def __str__(self):
        return self.report_number

    @classmethod
    def generate_report_number(cls):
        from datetime import date
        return _next_sequential_number(cls, 'report_number', f'SRR-{date.today().year}-')

    def save(self, *args, **kwargs):
        if not self.report_number:
            self.report_number = self.generate_report_number()
        super().save(*args, **kwargs)


class JobOrder(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    job_order_number = models.CharField(max_length=50, unique=True)
    names = models.TextField(blank=True, default='', help_text='One or more assignee names, one per line.')
    date_filed = models.DateField()
    dates_covered = models.TextField(blank=True, default='', help_text='Coverage date or date range entries, one per line.')
    area_assignment = models.TextField(blank=True, default='')
    job_description = models.TextField()
    prepared_by = models.CharField(max_length=200, blank=True, default='')
    noted_by = models.CharField(max_length=200, blank=True, default='')
    approved_by = models.CharField(max_length=200, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_filed', '-created_at']

    def __str__(self):
        return self.job_order_number

    @classmethod
    def generate_job_order_number(cls):
        from datetime import date
        return _next_sequential_number(cls, 'job_order_number', f'JO-{date.today().year}-')

    def save(self, *args, **kwargs):
        if not self.job_order_number:
            self.job_order_number = self.generate_job_order_number()
        super().save(*args, **kwargs)

    @property
    def names_display(self):
        return ', '.join(line.strip() for line in self.names.splitlines() if line.strip()) or '—'

    @property
    def dates_covered_display(self):
        return ', '.join(line.strip() for line in self.dates_covered.splitlines() if line.strip()) or '—'


class OfficialBusinessForm(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    name = models.CharField(max_length=200)
    designation = models.CharField(max_length=200, blank=True, default='')
    application_date = models.DateField()
    ob_dates = models.TextField(blank=True, default='', help_text='One OB date per line.')
    destination = models.TextField(blank=True, default='', help_text='OB address / destination.')
    time_departure = models.TimeField(null=True, blank=True)
    time_return = models.TimeField(null=True, blank=True)
    purpose = models.TextField(blank=True, default='')
    prepared_by = models.CharField(max_length=200, blank=True, default='', help_text="Employee's name & signature.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    APPROVER_NAME = 'ENGR. ARTURO I. DAVIS, PME'
    APPROVER_TITLE = 'PRESIDENT/GEN. MANAGER'

    class Meta:
        ordering = ['-application_date', '-created_at']

    def __str__(self):
        return f'{self.name} – {self.application_date}'

    @property
    def ob_dates_display(self):
        return ', '.join(line.strip() for line in self.ob_dates.splitlines() if line.strip()) or '—'

    @property
    def approved_by_display(self):
        return f'{self.APPROVER_NAME} ({self.APPROVER_TITLE})'


class TravelOrderForm(models.Model):
    travel_date = models.DateField()
    driver_name = models.CharField(max_length=200)
    travel_with = models.TextField(blank=True, default='', help_text='One passenger name per line.')
    destination = models.CharField(max_length=300, blank=True, default='')
    purpose = models.TextField(blank=True, default='')
    departure_time = models.TimeField(null=True, blank=True)
    vehicle_plate = models.CharField(max_length=200, blank=True, default='')
    fuel_allowance = models.CharField(max_length=200, blank=True, default='', help_text='PO# / Amount / Liters')
    approved_by = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    ISSUER_NAME = 'AIZA MAE POQUITA'

    class Meta:
        ordering = ['-travel_date', '-created_at']

    def __str__(self):
        return f'{self.driver_name} – {self.travel_date}'

    @property
    def travel_with_display(self):
        names = [line.strip() for line in self.travel_with.splitlines() if line.strip()]
        return '\n'.join(names) if names else '—'

    @property
    def issued_by_display(self):
        return self.ISSUER_NAME


class MaterialBorrow(models.Model):
    STATUS_CHOICES = [
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
        ('partial', 'Partially Returned'),
        ('overdue', 'Overdue'),
    ]

    borrow_number = models.CharField(max_length=50, unique=True)
    date_borrowed = models.DateField()
    borrower_name = models.CharField(max_length=200)
    department = models.CharField(max_length=200, blank=True, default='')
    purpose = models.TextField(blank=True, default='')
    expected_return_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True, default='')
    prepared_by = models.CharField(max_length=200, blank=True, default='')
    noted_by = models.CharField(max_length=200, blank=True, default='')
    approved_by = models.CharField(max_length=200, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='borrowed')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_borrowed', '-created_at']

    def __str__(self):
        return self.borrow_number

    @classmethod
    def generate_borrow_number(cls):
        from datetime import date
        return _next_sequential_number(cls, 'borrow_number', f'BM-{date.today().year}-')

    def save(self, *args, **kwargs):
        if not self.borrow_number:
            self.borrow_number = self.generate_borrow_number()
        super().save(*args, **kwargs)


class MaterialBorrowLine(models.Model):
    material_borrow = models.ForeignKey(
        MaterialBorrow,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='borrow_lines',
    )
    item_description = models.CharField(max_length=300)
    quantity = models.PositiveIntegerField(default=1)
    unit = models.CharField(max_length=50, blank=True, default='pcs')
    remarks = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.item_description} x{self.quantity}'


class DeliveryReceipt(models.Model):
    receipt_number = models.CharField(max_length=50, unique=True)
    receipt_date = models.DateField()
    delivered_to = models.CharField(max_length=200)
    tin = models.CharField(max_length=50, blank=True, default='')
    po_number = models.CharField(max_length=100, blank=True, default='')
    address = models.TextField(blank=True, default='')
    terms = models.CharField(max_length=100, blank=True, default='')
    certified_by = models.CharField(max_length=200, blank=True, default='')
    delivered_by = models.CharField(max_length=200, blank=True, default='')
    received_by = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-receipt_date', '-created_at']

    def __str__(self):
        return self.receipt_number

    @classmethod
    def generate_receipt_number(cls):
        from datetime import date
        return _next_sequential_number(cls, 'receipt_number', f'DR-{date.today().year}-')

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        super().save(*args, **kwargs)

    @property
    def total_amount(self):
        return sum((line.amount for line in self.lines.all()), Decimal('0'))


class DeliveryReceiptLine(models.Model):
    delivery_receipt = models.ForeignKey(
        DeliveryReceipt,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delivery_receipt_lines',
    )
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit = models.CharField(max_length=50, blank=True, default='pcs')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.description} x{self.quantity}'

    @property
    def amount(self):
        return (self.quantity or Decimal('0')) * (self.unit_price or Decimal('0'))


class WorkspaceAccount(models.Model):
    """Temporary demo credentials for each dashboard workspace."""

    workspace_key = models.CharField(max_length=50, unique=True)
    workspace_name = models.CharField(max_length=100)
    dashboard_url_name = models.CharField(max_length=100)
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='workspace_account',
    )
    username = models.CharField(max_length=150)
    temporary_password = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['workspace_name']

    def __str__(self):
        return f'{self.workspace_name} ({self.username})'


# ========== ACCOUNTING MODELS ==========
# Fresh, self-contained double-entry accounting module. Deliberately NOT wired to
# SalesOrder / Quotation / ServiceQuotation / RefundRecord / PayrollRun / Delivery —
# accounting staff record transactions directly here.

class Account(models.Model):
    """Chart of Accounts entry."""

    ACCOUNT_TYPES = [
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('equity', 'Equity'),
        ('revenue', 'Revenue'),
        ('expense', 'Expense'),
    ]
    CATEGORY_CHOICES = [
        ('cash', 'Cash'),
        ('bank', 'Bank'),
        ('ar', 'Accounts Receivable'),
        ('inventory', 'Inventory'),
        ('tax_input', 'Input VAT'),
        ('fixed_asset', 'Fixed Asset'),
        ('ap', 'Accounts Payable'),
        ('tax_output', 'Output VAT Payable'),
        ('tax_payable', 'Other Tax Payable'),
        ('loan_payable', 'Loans Payable'),
        ('equity', 'Equity'),
        ('revenue', 'Revenue'),
        ('cogs', 'Cost of Goods Sold'),
        ('operating_expense', 'Operating Expense'),
        ('other', 'Other'),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    description = models.CharField(max_length=255, blank=True, default='')
    is_system = models.BooleanField(default=False, help_text='Seeded accounts required by auto-posting; cannot be deleted.')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} – {self.name}'

    @property
    def normal_balance(self):
        return 'debit' if self.account_type in ('asset', 'expense') else 'credit'

    @property
    def current_balance(self):
        totals = self.lines.aggregate(total_debit=models.Sum('debit'), total_credit=models.Sum('credit'))
        debit = totals['total_debit'] or Decimal('0')
        credit = totals['total_credit'] or Decimal('0')
        if self.normal_balance == 'debit':
            return debit - credit
        return credit - debit


class JournalEntry(models.Model):
    """Header for a balanced set of debit/credit lines (the General Ledger source)."""

    SOURCE_TYPES = [
        ('manual', 'Manual'),
        ('invoice', 'Invoice'),
        ('invoice_payment', 'Invoice Payment'),
        ('bill', 'Bill'),
        ('bill_payment', 'Bill Payment'),
        ('bank_transaction', 'Bank Transaction'),
        ('payroll_expense', 'Payroll Expense'),
        ('opening_balance', 'Opening Balance'),
        ('reversal', 'Reversal'),
    ]

    entry_number = models.CharField(max_length=30, unique=True)
    entry_date = models.DateField()
    memo = models.CharField(max_length=255, blank=True, default='')
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPES, default='manual')
    source_id = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='journal_entries',
    )
    is_void = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-entry_date', '-created_at']

    def __str__(self):
        return self.entry_number

    @property
    def total_debit(self):
        return sum((line.debit for line in self.lines.all()), Decimal('0'))

    @property
    def total_credit(self):
        return sum((line.credit for line in self.lines.all()), Decimal('0'))


class JournalEntryLine(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='lines')
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.journal_entry.entry_number} – {self.account.code}'


class BankAccount(models.Model):
    ACCOUNT_TYPES = [
        ('bank', 'Bank'),
        ('cash_on_hand', 'Cash on Hand'),
    ]

    name = models.CharField(max_length=150)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='bank')
    bank_name = models.CharField(max_length=150, blank=True, default='')
    account_number = models.CharField(max_length=100, blank=True, default='')
    gl_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='bank_accounts')
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    opening_balance_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def current_balance(self):
        """Opening balance is stored directly (never journaled), so add it to the GL activity."""
        return self.opening_balance + self.gl_account.current_balance


class BankTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('transfer', 'Transfer'),
    ]

    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name='transactions')
    transaction_date = models.DateField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, default='deposit')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    contra_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True, related_name='bank_contra_transactions',
        help_text='Used for deposits/withdrawals (e.g. Owner\'s Capital, Other Income).',
    )
    to_bank_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, null=True, blank=True, related_name='incoming_transfers',
        help_text='Used for transfers between bank/cash accounts.',
    )
    reference = models.CharField(max_length=100, blank=True, default='')
    description = models.CharField(max_length=255, blank=True, default='')
    related_journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transaction_date', '-created_at']

    def __str__(self):
        return f'{self.get_transaction_type_display()} – {self.bank_account} – {self.amount}'


class Customer(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=150, blank=True, default='')
    phone = models.CharField(max_length=50, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    address = models.TextField(blank=True, default='')
    tax_id = models.CharField(max_length=50, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Invoice(models.Model):
    """Accounts Receivable — independent of SalesOrder/Quotation."""

    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]

    invoice_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices')
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, help_text='VAT-inclusive gross amount')
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    revenue_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='invoices')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True, default='')
    related_journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-invoice_date', '-created_at']

    def __str__(self):
        return self.invoice_number

    @property
    def balance_due(self):
        return self.amount - self.paid_amount

    def refresh_status(self):
        if self.paid_amount >= self.amount:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        elif self.due_date and self.due_date < date.today():
            self.status = 'overdue'
        else:
            self.status = 'unpaid'


class InvoicePayment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name='invoice_payments')
    reference = models.CharField(max_length=100, blank=True, default='')
    related_journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f'Payment {self.amount} – {self.invoice}'


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=150, blank=True, default='')
    phone = models.CharField(max_length=50, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    address = models.TextField(blank=True, default='')
    tax_id = models.CharField(max_length=50, blank=True, default='')
    payment_terms = models.CharField(max_length=150, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Bill(models.Model):
    """Accounts Payable / Purchases — independent of Delivery/DeliveryLine."""

    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]

    bill_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='bills')
    bill_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, help_text='VAT-inclusive gross amount')
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expense_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='bills')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True, default='')
    related_journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-bill_date', '-created_at']

    def __str__(self):
        return self.bill_number

    @property
    def balance_due(self):
        return self.amount - self.paid_amount

    def refresh_status(self):
        if self.paid_amount >= self.amount:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        elif self.due_date and self.due_date < date.today():
            self.status = 'overdue'
        else:
            self.status = 'unpaid'


class BillPayment(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name='bill_payments')
    reference = models.CharField(max_length=100, blank=True, default='')
    related_journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f'Payment {self.amount} – {self.bill}'


class PayrollExpenseEntry(models.Model):
    """Manual payroll cost entry — independent of PayrollRun."""

    entry_date = models.DateField()
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name='payroll_expense_entries')
    expense_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='payroll_expense_entries')
    related_journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-entry_date', '-created_at']

    def __str__(self):
        return f'{self.entry_date} – {self.description} ({self.amount})'


class TaxDeadline(models.Model):
    TAX_TYPES = [
        ('vat', 'VAT (BIR Form 2550Q)'),
        ('withholding_compensation', 'Withholding Tax on Compensation (1601-C)'),
        ('income_tax_quarterly', 'Quarterly Income Tax (1701Q/1702Q)'),
        ('income_tax_annual', 'Annual Income Tax'),
    ]

    name = models.CharField(max_length=200)
    tax_type = models.CharField(max_length=30, choices=TAX_TYPES)
    period_start = models.DateField()
    period_end = models.DateField()
    due_date = models.DateField()
    is_filed = models.BooleanField(default=False)
    filed_date = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['due_date']

    def __str__(self):
        return f'{self.name} – due {self.due_date}'

    @property
    def is_overdue(self):
        return not self.is_filed and self.due_date < date.today()


# ========== WATER BILLING MODELS ==========

WATER_CUSTOMER_TYPES = [
    ('residential', 'Residential'),
    ('commercial', 'Commercial'),
    ('government', 'Government'),
    ('industrial', 'Industrial'),
]

WATER_CONNECTION_STATUS = [
    ('active', 'Active'),
    ('inactive', 'Inactive'),
    ('disconnected', 'Disconnected'),
]

WATER_PAYMENT_METHODS = [
    ('cash', 'Cash'),
    ('bank', 'Bank'),
    ('online', 'Online Payment'),
    ('ewallet', 'E-Wallet'),
]

WATER_BILL_STATUS = [
    ('unpaid', 'Unpaid'),
    ('partial', 'Partial'),
    ('paid', 'Paid'),
    ('overdue', 'Overdue'),
    ('cancelled', 'Cancelled'),
]

WATER_SERVICE_ACTION_TYPES = [
    ('disconnection', 'Disconnection'),
    ('reconnection', 'Reconnection'),
]

WATER_SERVICE_ACTION_STATUS = [
    ('scheduled', 'Scheduled'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]


class WaterCustomer(models.Model):
    account_number = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=200)
    service_address = models.TextField()
    contact_number = models.CharField(max_length=50, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    customer_type = models.CharField(max_length=20, choices=WATER_CUSTOMER_TYPES, default='residential')
    meter_number = models.CharField(max_length=50, unique=True)
    connection_status = models.CharField(max_length=20, choices=WATER_CONNECTION_STATUS, default='active')
    registration_date = models.DateField(default=date.today)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.account_number} – {self.full_name}'

    @classmethod
    def generate_account_number(cls):
        return _next_sequential_number(cls, 'account_number', f'WA-{date.today().year}-')

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = self.generate_account_number()
        super().save(*args, **kwargs)

    @property
    def outstanding_balance(self):
        total = Decimal('0.00')
        for bill in self.bills.exclude(status='cancelled'):
            total += bill.balance_due
        return total


class WaterMeterReading(models.Model):
    customer = models.ForeignKey(WaterCustomer, on_delete=models.CASCADE, related_name='readings')
    reading_date = models.DateField()
    billing_period = models.CharField(max_length=20, help_text='e.g. 2026-07')
    previous_reading = models.PositiveIntegerField(default=0)
    current_reading = models.PositiveIntegerField()
    consumption = models.PositiveIntegerField(default=0)
    is_estimated = models.BooleanField(default=False)
    reader_name = models.CharField(max_length=200, blank=True, default='')
    remarks = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-reading_date', '-created_at']
        unique_together = [('customer', 'billing_period')]

    def __str__(self):
        return f'{self.customer.account_number} – {self.billing_period}'

    def save(self, *args, **kwargs):
        prev = int(self.previous_reading or 0)
        curr = int(self.current_reading or 0)
        if curr < prev:
            raise ValueError('Current reading cannot be lower than previous reading.')
        self.consumption = curr - prev
        super().save(*args, **kwargs)


class WaterBill(models.Model):
    bill_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(WaterCustomer, on_delete=models.CASCADE, related_name='bills')
    meter_reading = models.OneToOneField(
        WaterMeterReading, on_delete=models.SET_NULL, null=True, blank=True, related_name='bill',
    )
    billing_period = models.CharField(max_length=20)
    bill_date = models.DateField()
    due_date = models.DateField()
    consumption = models.PositiveIntegerField(default=0)
    rate_per_cum = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('25.00'))
    consumption_charge = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    fixed_charge = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('50.00'))
    environmental_fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('10.00'))
    maintenance_fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('15.00'))
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    penalty = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=WATER_BILL_STATUS, default='unpaid')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-bill_date', '-created_at']

    def __str__(self):
        return self.bill_number

    @classmethod
    def generate_bill_number(cls):
        return _next_sequential_number(cls, 'bill_number', f'WB-{date.today().year}-')

    @property
    def balance_due(self):
        return max(self.total_amount - self.amount_paid, Decimal('0.00'))

    def recompute_totals(self):
        self.consumption_charge = (Decimal(self.consumption or 0) * self.rate_per_cum).quantize(Decimal('0.01'))
        self.total_amount = (
            self.consumption_charge
            + self.fixed_charge
            + self.environmental_fee
            + self.maintenance_fee
            + self.tax
            + self.penalty
            - self.discount
        ).quantize(Decimal('0.01'))
        if self.total_amount < 0:
            self.total_amount = Decimal('0.00')
        self.refresh_status()

    def refresh_status(self):
        if self.status == 'cancelled':
            return
        if self.amount_paid <= 0:
            self.status = 'overdue' if self.due_date < date.today() else 'unpaid'
        elif self.amount_paid >= self.total_amount:
            self.status = 'paid'
            self.amount_paid = self.total_amount
        else:
            self.status = 'partial'

    def save(self, *args, **kwargs):
        if not self.bill_number:
            self.bill_number = self.generate_bill_number()
        self.recompute_totals()
        super().save(*args, **kwargs)


class WaterPayment(models.Model):
    receipt_number = models.CharField(max_length=50, unique=True)
    bill = models.ForeignKey(WaterBill, on_delete=models.CASCADE, related_name='payments')
    customer = models.ForeignKey(WaterCustomer, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=WATER_PAYMENT_METHODS, default='cash')
    reference_number = models.CharField(max_length=100, blank=True, default='')
    received_by = models.CharField(max_length=200, blank=True, default='')
    remarks = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f'{self.receipt_number} – {self.amount}'

    @classmethod
    def generate_receipt_number(cls):
        return _next_sequential_number(cls, 'receipt_number', f'WP-{date.today().year}-')

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        if self.customer_id is None and self.bill_id:
            self.customer = self.bill.customer
        super().save(*args, **kwargs)


class WaterServiceAction(models.Model):
    customer = models.ForeignKey(WaterCustomer, on_delete=models.CASCADE, related_name='service_actions')
    action_type = models.CharField(max_length=20, choices=WATER_SERVICE_ACTION_TYPES)
    action_date = models.DateField()
    status = models.CharField(max_length=20, choices=WATER_SERVICE_ACTION_STATUS, default='scheduled')
    reason = models.TextField(blank=True, default='')
    reconnection_fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('500.00'))
    fee_paid = models.BooleanField(default=False)
    performed_by = models.CharField(max_length=200, blank=True, default='')
    notes = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-action_date', '-created_at']

    def __str__(self):
        return f'{self.get_action_type_display()} – {self.customer.account_number}'


class WaterAuditLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    username = models.CharField(max_length=150, blank=True, default='')
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=50, blank=True, default='')
    details = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.timestamp:%Y-%m-%d %H:%M} – {self.action}'

