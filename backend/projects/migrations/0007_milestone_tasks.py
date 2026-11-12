from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0006_change_application'),
        ('tasks', '0002_task_actual_duration_days_task_actual_end_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='milestone',
            name='tasks',
            field=models.ManyToManyField(
                blank=True, related_name='milestones', to='tasks.task'
            ),
        ),
    ]
