import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('projects', '0007_milestone_tasks')]

    operations = [
        migrations.CreateModel(
            name='MilestoneKPI',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True, default='')),
                ('responsible', models.CharField(max_length=150)),
                ('kind', models.CharField(choices=[('VALUE', 'Valor directo'), ('PERCENTAGE', 'Porcentaje (numerador / denominador)')], default='VALUE', max_length=12)),
                ('direction', models.CharField(choices=[('AT_LEAST', 'Mayor o igual a la meta'), ('AT_MOST', 'Menor o igual a la meta')], default='AT_LEAST', max_length=12)),
                ('unit', models.CharField(default='unidad', max_length=30)),
                ('target_value', models.DecimalField(decimal_places=2, max_digits=15)),
                ('measured_value', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('numerator', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('denominator', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('measured_at', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('milestone', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kpis', to='projects.milestone')),
            ],
            options={
                'db_table': 'project_milestone_kpis',
                'ordering': ['milestone_id', 'id'],
            },
        ),
    ]
