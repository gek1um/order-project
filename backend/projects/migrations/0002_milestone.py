from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('projects', '0001_initial')]
    operations = [
        migrations.CreateModel(
            name='Milestone',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('due_date', models.DateField()),
                ('responsible', models.CharField(max_length=150)),
                ('acceptance_criteria', models.TextField()),
                ('evidence', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('PENDING', 'Pendiente'), ('COMPLETED', 'Cumplido')], default='PENDING', max_length=12)),
                ('completed_at', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='milestones', to='projects.project')),
            ],
            options={'db_table': 'project_milestones', 'ordering': ['due_date', 'id']},
        ),
    ]
