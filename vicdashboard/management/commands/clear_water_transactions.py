"""Delete water billing transactions. Keeps customers, zones, and contracts."""

from django.core.management.base import BaseCommand
from django.db import transaction

from vicdashboard.models import (
    WaterAuditLog,
    WaterBill,
    WaterCustomer,
    WaterMeterReading,
    WaterPayment,
    WaterServiceAction,
    WaterServiceContract,
    WaterWeeklyReport,
    WaterZone,
)


class Command(BaseCommand):
    help = (
        'Delete all water payments, bills, readings, service actions, weekly reports, '
        'and audit logs. Keeps customers, zones, and service contracts. Sets customers Active.'
    )

    def handle(self, *args, **options):
        before = {
            'customers': WaterCustomer.objects.count(),
            'zones': WaterZone.objects.count(),
            'contracts': WaterServiceContract.objects.count(),
            'payments': WaterPayment.objects.count(),
            'bills': WaterBill.objects.count(),
            'readings': WaterMeterReading.objects.count(),
            'service_actions': WaterServiceAction.objects.count(),
            'weekly_reports': WaterWeeklyReport.objects.count(),
            'audits': WaterAuditLog.objects.count(),
        }
        self.stdout.write('Before:')
        for key, count in before.items():
            self.stdout.write(f'  {key}: {count}')

        with transaction.atomic():
            deleted_payments, _ = WaterPayment.objects.all().delete()
            deleted_bills, _ = WaterBill.objects.all().delete()
            deleted_readings, _ = WaterMeterReading.objects.all().delete()
            deleted_actions, _ = WaterServiceAction.objects.all().delete()
            deleted_reports, _ = WaterWeeklyReport.objects.all().delete()
            deleted_audits, _ = WaterAuditLog.objects.all().delete()
            WaterCustomer.objects.exclude(connection_status='active').update(connection_status='active')

        after = {
            'customers': WaterCustomer.objects.count(),
            'zones': WaterZone.objects.count(),
            'contracts': WaterServiceContract.objects.count(),
            'payments': WaterPayment.objects.count(),
            'bills': WaterBill.objects.count(),
            'readings': WaterMeterReading.objects.count(),
            'service_actions': WaterServiceAction.objects.count(),
            'weekly_reports': WaterWeeklyReport.objects.count(),
            'audits': WaterAuditLog.objects.count(),
        }
        self.stdout.write(self.style.SUCCESS(
            f'Deleted payments={deleted_payments} bills={deleted_bills} '
            f'readings={deleted_readings} actions={deleted_actions} '
            f'reports={deleted_reports} audits={deleted_audits}'
        ))
        self.stdout.write('After:')
        for key, count in after.items():
            self.stdout.write(f'  {key}: {count}')
        if after['customers'] != before['customers']:
            raise SystemExit('Customer count changed; abort expected invariant.')
        self.stdout.write(self.style.SUCCESS(
            f'Customers unchanged: {after["customers"]}. All set to Active.'
        ))
