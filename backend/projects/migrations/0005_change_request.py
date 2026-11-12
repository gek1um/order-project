from decimal import Decimal
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [('projects', '0004_taskresourceassignment')]

    operations = [
        migrations.CreateModel(
            name='ChangeRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('requester', models.CharField(max_length=150)),
                ('requested_at', models.DateField(default=django.utils.timezone.localdate)),
                ('description', models.TextField()),
                ('justification', models.TextField()),
                ('kind', models.CharField(max_length=16, choices=[('SCOPE', 'Alcance'), ('TIME', 'Tiempo'), ('COST', 'Costo'), ('RESOURCE', 'Recursos'), ('TECHNOLOGY', 'Tecnología'), ('ORGANIZATION', 'Organización')])),
                ('priority', models.CharField(max_length=12, choices=[('LOW', 'Baja'), ('MEDIUM', 'Media'), ('HIGH', 'Alta'), ('CRITICAL', 'Crítica')], default='MEDIUM')),
                ('risk', models.TextField(blank=True, default='')),
                ('impact_scope', models.TextField(blank=True, default='')),
                ('impact_resources', models.TextField(blank=True, default='')),
                ('estimated_delay_days', models.IntegerField(default=0, help_text='Impacto estimado en días calendario; positivo = retraso.')),
                ('estimated_cost', models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))),
                ('actual_cost', models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)),
                ('responsible', models.CharField(max_length=150, blank=True, default='')),
                ('committed_date', models.DateField(null=True, blank=True)),
                ('actual_completion_date', models.DateField(null=True, blank=True)),
                ('result', models.TextField(blank=True, default='')),
                ('status', models.CharField(max_length=20, choices=[('OPEN', 'Abierta'), ('UNDER_REVIEW', 'En evaluación'), ('APPROVED', 'Aprobada'), ('REJECTED', 'Rechazada'), ('IMPLEMENTING', 'En implementación'), ('CLOSED', 'Cerrada')], default='OPEN')),
                ('decided_by', models.CharField(max_length=150, blank=True, default='')),
                ('decided_at', models.DateTimeField(null=True, blank=True)),
                ('decision_reason', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='change_requests', to='projects.project')),
            ],
            options={'db_table': 'project_change_requests', 'ordering': ['-created_at', '-id']},
        ),
        migrations.CreateModel(
            name='ChangeEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=30)),
                ('from_status', models.CharField(max_length=20, blank=True, default='')),
                ('to_status', models.CharField(max_length=20)),
                ('actor', models.CharField(max_length=150)),
                ('detail', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('change_request', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='events', to='projects.changerequest')),
            ],
            options={'db_table': 'project_change_events', 'ordering': ['created_at', 'id']},
        ),
        migrations.AddConstraint(
            model_name='changerequest',
            constraint=models.CheckConstraint(condition=Q(estimated_cost__gte=0), name='change_estimated_cost_nonnegative'),
        ),
        migrations.AddConstraint(
            model_name='changerequest',
            constraint=models.CheckConstraint(condition=Q(actual_cost__isnull=True) | Q(actual_cost__gte=0), name='change_actual_cost_nonnegative'),
        ),
    ]
