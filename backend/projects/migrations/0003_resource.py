from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("projects", "0002_milestone")]

    operations = [
        migrations.CreateModel(
            name="Resource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=24, choices=[("PROFESSIONAL", "Profesional"), ("PROFESSIONAL_TYPE", "Tipo de profesional"), ("LICENSE", "Licencia de software"), ("MATERIAL", "Material"), ("EQUIPMENT", "Equipamiento"), ("OTHER", "Otro")])),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                ("specialty", models.CharField(max_length=120, blank=True, default="")),
                ("unit", models.CharField(max_length=40, blank=True, default="")),
                ("hours_per_week", models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)),
                ("weeks", models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)),
                ("hourly_rate", models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True)),
                ("quantity", models.DecimalField(max_digits=11, decimal_places=2, default=Decimal("1"))),
                ("unit_cost", models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True)),
                ("periods", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(to="projects.project", on_delete=django.db.models.deletion.PROTECT, related_name="resources")),
            ],
            options={"db_table": "project_resources", "ordering": ["kind", "name", "id"]},
        ),
        migrations.AddConstraint(model_name="resource", constraint=models.CheckConstraint(condition=Q(quantity__gt=0), name="resource_quantity_positive")),
        migrations.AddConstraint(model_name="resource", constraint=models.CheckConstraint(condition=Q(periods__gte=1), name="resource_periods_positive")),
        migrations.AddConstraint(model_name="resource", constraint=models.CheckConstraint(condition=Q(hours_per_week__isnull=True) | Q(hours_per_week__gt=0), name="resource_hours_positive")),
        migrations.AddConstraint(model_name="resource", constraint=models.CheckConstraint(condition=Q(weeks__isnull=True) | Q(weeks__gt=0), name="resource_weeks_positive")),
        migrations.AddConstraint(model_name="resource", constraint=models.CheckConstraint(condition=Q(hourly_rate__isnull=True) | Q(hourly_rate__gte=0), name="resource_rate_nonnegative")),
        migrations.AddConstraint(model_name="resource", constraint=models.CheckConstraint(condition=Q(unit_cost__isnull=True) | Q(unit_cost__gte=0), name="resource_unit_cost_nonnegative")),
    ]
