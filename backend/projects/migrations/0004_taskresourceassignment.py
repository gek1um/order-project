from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0003_resource'),
        ('tasks', '0002_task_actual_duration_days_task_actual_end_date_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskResourceAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('planned_units', models.DecimalField(decimal_places=2, max_digits=12)),
                ('actual_units', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('planned_unit_cost', models.DecimalField(decimal_places=2, max_digits=15)),
                ('actual_unit_cost', models.DecimalField(decimal_places=2, max_digits=15)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('resource', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='task_assignments', to='projects.resource')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='resource_assignments', to='tasks.task')),
            ],
            options={
                'db_table': 'task_resource_assignments',
                'ordering': ['task_id', 'id'],
            },
        ),
        migrations.AddConstraint(model_name='taskresourceassignment', constraint=models.CheckConstraint(condition=models.Q(('planned_units__gt', 0)), name='assignment_planned_units_positive')),
        migrations.AddConstraint(model_name='taskresourceassignment', constraint=models.CheckConstraint(condition=models.Q(('actual_units__gte', 0)), name='assignment_actual_units_nonnegative')),
        migrations.AddConstraint(model_name='taskresourceassignment', constraint=models.CheckConstraint(condition=models.Q(('planned_unit_cost__gte', 0)), name='assignment_planned_cost_nonnegative')),
        migrations.AddConstraint(model_name='taskresourceassignment', constraint=models.CheckConstraint(condition=models.Q(('actual_unit_cost__gte', 0)), name='assignment_actual_cost_nonnegative')),
    ]
