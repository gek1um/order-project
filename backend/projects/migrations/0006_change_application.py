import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0005_change_request'),
        ('tasks', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChangeApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(max_length=20, choices=[('SCHEDULE', 'Reprogramación'), ('COST', 'Registro de costo real')])),
                ('actor', models.CharField(max_length=150)),
                ('before', models.JSONField(default=dict)),
                ('after', models.JSONField(default=dict)),
                ('detail', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('change_request', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='applications', to='projects.changerequest')),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='change_applications', to='tasks.task')),
            ],
            options={'db_table': 'project_change_applications', 'ordering': ['created_at', 'id']},
        ),
    ]
