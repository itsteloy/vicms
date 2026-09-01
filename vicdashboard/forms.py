from django import forms

from .models import DeliveryReceipt, Company, Employee, JobOrder, JobOrderIdlePeriod, MaterialBorrow, OfficialBusinessForm, Position, ServiceRepairReport, TravelOrderForm, WithdrawalSlip


class ServiceRepairReportForm(forms.ModelForm):
    class Meta:
        model = ServiceRepairReport
        exclude = ('created_at', 'updated_at')
        widgets = {
            'report_date': forms.DateInput(attrs={'type': 'date'}),
            'complaint': forms.Textarea(attrs={'rows': 4}),
            'customer_address': forms.Textarea(attrs={'rows': 3}),
            'diagnosis': forms.Textarea(attrs={'rows': 4}),
            'repairs_performed': forms.Textarea(attrs={'rows': 4}),
            'parts_used': forms.Textarea(attrs={'rows': 3}),
            'recommendations': forms.Textarea(attrs={'rows': 3}),
        }


class JobOrderForm(forms.ModelForm):
    class Meta:
        model = JobOrder
        exclude = ('created_at', 'updated_at', 'status')
        widgets = {
            'date_filed': forms.DateInput(attrs={'type': 'date'}),
            'coverage_start': forms.DateInput(attrs={'type': 'date'}),
            'coverage_end': forms.DateInput(attrs={'type': 'date'}),
            'assignees': forms.SelectMultiple(attrs={'size': 8}),
            'names': forms.Textarea(attrs={'rows': 3, 'placeholder': 'One name per line (auto-filled from assignees)'}),
            'dates_covered': forms.Textarea(attrs={'rows': 3, 'placeholder': 'One date or range per line'}),
            'area_assignment': forms.Textarea(attrs={'rows': 3}),
            'job_description': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignees'].queryset = Employee.objects.filter(
            termination_date__isnull=True
        ).order_by('last_name', 'first_name')
        self.fields['assignees'].required = False
        self.fields['coverage_start'].required = False
        self.fields['coverage_end'].required = False
        self.fields['names'].required = False
        self.fields['dates_covered'].required = False

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('coverage_start')
        end = cleaned.get('coverage_end')
        if start and end and end < start:
            self.add_error('coverage_end', 'Coverage end must be on or after coverage start.')
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            instance.sync_legacy_text_fields()
        return instance


class JobOrderIdlePeriodForm(forms.ModelForm):
    class Meta:
        model = JobOrderIdlePeriod
        fields = ('start_date', 'end_date', 'reason', 'notes')
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.TextInput(attrs={'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, job_order=None, **kwargs):
        self.job_order = job_order
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        if self.job_order is not None:
            self.instance.job_order = self.job_order
        self.instance.start_date = cleaned.get('start_date') or self.instance.start_date
        self.instance.end_date = cleaned.get('end_date') or self.instance.end_date
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            self.instance.clean()
        except DjangoValidationError as exc:
            if hasattr(exc, 'message_dict'):
                for field, errors in exc.message_dict.items():
                    for error in errors:
                        self.add_error(field if field in self.fields else None, error)
            else:
                self.add_error(None, exc)
        return cleaned


class OfficialBusinessFormForm(forms.ModelForm):
    class Meta:
        model = OfficialBusinessForm
        exclude = ('created_at', 'updated_at', 'status', 'approved_at')
        widgets = {
            'application_date': forms.DateInput(attrs={'type': 'date'}),
            'ob_dates': forms.Textarea(attrs={'rows': 3, 'placeholder': 'One date or range per line'}),
            'destination': forms.Textarea(attrs={'rows': 2}),
            'time_departure': forms.TimeInput(attrs={'type': 'time'}),
            'time_return': forms.TimeInput(attrs={'type': 'time'}),
            'purpose': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.employee_map = {
            emp.full_name: emp
            for emp in Employee.objects.select_related('position')
            .filter(termination_date__isnull=True)
            .order_by('last_name', 'first_name')
        }
        employee_choices = [('', 'Select employee')] + [
            (name, f'{name} ({emp.employee_id})')
            for name, emp in self.employee_map.items()
        ]
        self.fields['name'] = forms.ChoiceField(
            choices=employee_choices,
            required=True,
            initial=self.instance.name if self.instance and self.instance.pk else '',
            widget=forms.Select(attrs={'class': 'field-input'}),
        )
        self.fields['designation'].widget.attrs.update({
            'class': 'field-input',
            'readonly': 'readonly',
        })

    def clean(self):
        cleaned = super().clean()
        selected_name = cleaned.get('name', '').strip()
        employee = self.employee_map.get(selected_name)
        if employee:
            cleaned['designation'] = employee.position.title
            self.instance.designation = employee.position.title
        return cleaned


class TravelOrderFormForm(forms.ModelForm):
    class Meta:
        model = TravelOrderForm
        exclude = ('created_at', 'updated_at')
        widgets = {
            'travel_date': forms.DateInput(attrs={'type': 'date'}),
            'travel_with': forms.Textarea(attrs={'rows': 3, 'placeholder': 'One passenger name per line'}),
            'purpose': forms.Textarea(attrs={'rows': 2}),
            'departure_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class DeliveryReceiptForm(forms.ModelForm):
    class Meta:
        model = DeliveryReceipt
        exclude = ('created_at', 'updated_at')
        widgets = {
            'receipt_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }


class WithdrawalSlipForm(forms.ModelForm):
    class Meta:
        model = WithdrawalSlip
        exclude = ('created_at', 'updated_at')
        widgets = {
            'slip_date': forms.DateInput(attrs={'type': 'date'}),
        }


class MaterialBorrowForm(forms.ModelForm):
    class Meta:
        model = MaterialBorrow
        exclude = ('created_at', 'updated_at')
        widgets = {
            'date_borrowed': forms.DateInput(attrs={'type': 'date'}),
            'expected_return_date': forms.DateInput(attrs={'type': 'date'}),
            'purpose': forms.Textarea(attrs={'rows': 3}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            'last_name',
            'first_name',
            'daily_rate',
            'company',
            'position',
        ]
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'field-input uppercase-input', 'style': 'text-transform:uppercase'}),
            'first_name': forms.TextInput(attrs={'class': 'field-input uppercase-input', 'style': 'text-transform:uppercase'}),
            'daily_rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'field-input'}),
            'company': forms.Select(attrs={'class': 'field-input'}),
            'position': forms.Select(attrs={'class': 'field-input'}),
        }
