from django import forms

from .models import DeliveryReceipt, Department, Employee, JobOrder, MaterialBorrow, OfficialBusinessForm, Position, ServiceRepairReport, TravelOrderForm


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
            'names': forms.Textarea(attrs={'rows': 3, 'placeholder': 'One name per line'}),
            'dates_covered': forms.Textarea(attrs={'rows': 3, 'placeholder': 'One date or range per line'}),
            'area_assignment': forms.Textarea(attrs={'rows': 3}),
            'job_description': forms.Textarea(attrs={'rows': 5}),
        }


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
            'first_name',
            'last_name',
            'birth_date',
            'hire_date',
            'base_salary',
            'salary_frequency',
            'department',
            'position',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'field-input'}),
            'last_name': forms.TextInput(attrs={'class': 'field-input'}),
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'field-input'}),
            'hire_date': forms.DateInput(attrs={'type': 'date', 'class': 'field-input'}),
            'base_salary': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'field-input'}),
            'salary_frequency': forms.Select(attrs={'class': 'field-input'}),
            'department': forms.Select(attrs={'class': 'field-input'}),
            'position': forms.Select(attrs={'class': 'field-input'}),
        }
