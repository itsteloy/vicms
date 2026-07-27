from django.contrib.auth.hashers import make_password
from django.db import migrations

# The 'accounting' entry was added to 0019_seed_workspace_accounts.py after that
# migration had already been applied on existing databases, so it never actually ran.
# This migration seeds it directly so the Accounting Dashboard workspace account exists.
ACCOUNT = {
    'workspace_key': 'accounting',
    'workspace_name': 'Accounting',
    'dashboard_url_name': 'accounting_dashboard',
    'username': 'vic_accounting',
    'temporary_password': 'VicAcct2026!',
    'first_name': 'Accounting',
    'last_name': 'Workspace',
}


def seed_accounting_workspace_account(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    WorkspaceAccount = apps.get_model('vicdashboard', 'WorkspaceAccount')

    user, created = User.objects.get_or_create(
        username=ACCOUNT['username'],
        defaults={
            'first_name': ACCOUNT['first_name'],
            'last_name': ACCOUNT['last_name'],
            'email': f"{ACCOUNT['username']}@versatec.local",
            'password': make_password(ACCOUNT['temporary_password']),
            'is_staff': False,
            'is_superuser': False,
        },
    )
    if not created:
        user.password = make_password(ACCOUNT['temporary_password'])
        user.first_name = ACCOUNT['first_name']
        user.last_name = ACCOUNT['last_name']
        user.save(update_fields=['password', 'first_name', 'last_name'])

    WorkspaceAccount.objects.update_or_create(
        workspace_key=ACCOUNT['workspace_key'],
        defaults={
            'workspace_name': ACCOUNT['workspace_name'],
            'dashboard_url_name': ACCOUNT['dashboard_url_name'],
            'user': user,
            'username': ACCOUNT['username'],
            'temporary_password': ACCOUNT['temporary_password'],
            'is_active': True,
        },
    )


def unseed_accounting_workspace_account(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    WorkspaceAccount = apps.get_model('vicdashboard', 'WorkspaceAccount')
    WorkspaceAccount.objects.filter(username=ACCOUNT['username']).delete()
    User.objects.filter(username=ACCOUNT['username']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vicdashboard', '0025_seed_accounting_data'),
    ]

    operations = [
        migrations.RunPython(seed_accounting_workspace_account, unseed_accounting_workspace_account),
    ]
