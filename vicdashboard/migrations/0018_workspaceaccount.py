from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('vicdashboard', '0017_servicerepairreport_joborder'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkspaceAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('workspace_key', models.CharField(max_length=50, unique=True)),
                ('workspace_name', models.CharField(max_length=100)),
                ('dashboard_url_name', models.CharField(max_length=100)),
                ('username', models.CharField(max_length=150)),
                ('temporary_password', models.CharField(max_length=128)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='workspace_account', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['workspace_name'],
            },
        ),
    ]
