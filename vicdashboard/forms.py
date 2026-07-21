from django import forms

from .models import JobOrder, ServiceRepairReport


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
        exclude = ('created_at', 'updated_at')
        widgets = {
            'job_date': forms.DateInput(attrs={'type': 'date'}),
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
            'service_location': forms.Textarea(attrs={'rows': 3}),
            'scope_of_work': forms.Textarea(attrs={'rows': 5}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }
