from django.contrib.auth.hashers import make_password
from django.db import migrations


WORKSPACE_ACCOUNTS = [
    {
        'workspace_key': 'hr',
        'workspace_name': 'HR',
        'dashboard_url_name': 'hr_dashboard',
        'username': 'vic_hr',
        'temporary_password': 'VicHR2026!',
        'first_name': 'HR',
        'last_name': 'Workspace',
    },
    {
        'workspace_key': 'inventory',
        'workspace_name': 'Inventory',
        'dashboard_url_name': 'inventory_dashboard',
        'username': 'vic_inventory',
        'temporary_password': 'VicInv2026!',
        'first_name': 'Inventory',
        'last_name': 'Workspace',
    },
    {
        'workspace_key': 'sales',
        'workspace_name': 'Sales',
        'dashboard_url_name': 'sales_dashboard',
        'username': 'vic_sales',
        'temporary_password': 'VicSales2026!',
        'first_name': 'Sales',
        'last_name': 'Workspace',
    },
    {
        'workspace_key': 'payroll',
        'workspace_name': 'Payroll',
        'dashboard_url_name': 'payroll_dashboard',
        'username': 'vic_payroll',
        'temporary_password': 'VicPay2026!',
        'first_name': 'Payroll',
        'last_name': 'Workspace',
    },
    {
        'workspace_key': 'accounting',
        'workspace_name': 'Accounting',
        'dashboard_url_name': 'accounting_dashboard',
        'username': 'vic_accounting',
        'temporary_password': 'VicAcct2026!',
        'first_name': 'Accounting',
        'last_name': 'Workspace',
    },
    {
        'workspace_key': 'services',
        'workspace_name': 'Services',
        'dashboard_url_name': 'services_dashboard',
        'username': 'vic_services',
        'temporary_password': 'VicSvc2026!',
        'first_name': 'Services',
        'last_name': 'Workspace',
    },
]


def seed_workspace_accounts(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    WorkspaceAccount = apps.get_model('vicdashboard', 'WorkspaceAccount')

    for account in WORKSPACE_ACCOUNTS:
        user, created = User.objects.get_or_create(
            username=account['username'],
            defaults={
                'first_name': account['first_name'],
                'last_name': account['last_name'],
                'email': f"{account['username']}@versatec.local",
                'password': make_password(account['temporary_password']),
                'is_staff': False,
                'is_superuser': False,
            },
        )
        if not created:
            user.password = make_password(account['temporary_password'])
            user.first_name = account['first_name']
            user.last_name = account['last_name']
            user.save(update_fields=['password', 'first_name', 'last_name'])

        WorkspaceAccount.objects.update_or_create(
            workspace_key=account['workspace_key'],
            defaults={
                'workspace_name': account['workspace_name'],
                'dashboard_url_name': account['dashboard_url_name'],
                'user': user,
                'username': account['username'],
                'temporary_password': account['temporary_password'],
                'is_active': True,
            },
        )


def unseed_workspace_accounts(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    WorkspaceAccount = apps.get_model('vicdashboard', 'WorkspaceAccount')

    usernames = [account['username'] for account in WORKSPACE_ACCOUNTS]
    WorkspaceAccount.objects.filter(username__in=usernames).delete()
    User.objects.filter(username__in=usernames).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0018_workspaceaccount'),
    ]

    operations = [
        migrations.RunPython(seed_workspace_accounts, unseed_workspace_accounts),
    ]
