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
        return self.quotation_number or f'Quotation {self.pk}'


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        unique_together = ['employee', 'date']  # one log per employee per day

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


