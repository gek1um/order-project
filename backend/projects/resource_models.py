from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .models import Project


class Resource(models.Model):
    """Recurso presupuestable registrado en un proyecto.

    El costo estimado es una vista del catalogo, no un gasto comprometido.
    Las asignaciones y costos efectivos se incorporaran en la Fase 5.2.
    """

    class Kind(models.TextChoices):
        PROFESSIONAL = "PROFESSIONAL", "Profesional"
        PROFESSIONAL_TYPE = "PROFESSIONAL_TYPE", "Tipo de profesional"
        LICENSE = "LICENSE", "Licencia de software"
        MATERIAL = "MATERIAL", "Material"
        EQUIPMENT = "EQUIPMENT", "Equipamiento"
        OTHER = "OTHER", "Otro"

    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="resources"
    )
    kind = models.CharField(max_length=24, choices=Kind.choices)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    specialty = models.CharField(max_length=120, blank=True, default="")
    unit = models.CharField(max_length=40, blank=True, default="")

    # Profesionales y tipos: horas por semana * semanas * valor hora.
    hours_per_week = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    weeks = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    hourly_rate = models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True)

    # Materiales, licencias, equipos y otros: unidades * costo unitario.
    quantity = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal("1"))
    unit_cost = models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True)
    # Para una licencia o equipo arrendado, cantidad de periodos facturables.
    periods = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_resources"
        ordering = ["kind", "name", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="resource_quantity_positive"),
            models.CheckConstraint(condition=Q(periods__gte=1), name="resource_periods_positive"),
            models.CheckConstraint(condition=Q(hours_per_week__isnull=True) | Q(hours_per_week__gt=0), name="resource_hours_positive"),
            models.CheckConstraint(condition=Q(weeks__isnull=True) | Q(weeks__gt=0), name="resource_weeks_positive"),
            models.CheckConstraint(condition=Q(hourly_rate__isnull=True) | Q(hourly_rate__gte=0), name="resource_rate_nonnegative"),
            models.CheckConstraint(condition=Q(unit_cost__isnull=True) | Q(unit_cost__gte=0), name="resource_unit_cost_nonnegative"),
        ]

    @property
    def estimated_catalog_cost(self):
        if self.kind in (self.Kind.PROFESSIONAL, self.Kind.PROFESSIONAL_TYPE):
            if any(value is None for value in (self.hours_per_week, self.weeks, self.hourly_rate)):
                return None
            # Cantidad representa la dotacion necesaria; para profesional individual es 1.
            raw = self.quantity * self.hours_per_week * self.weeks * self.hourly_rate
        else:
            if self.unit_cost is None:
                return None
            raw = self.quantity * self.unit_cost
            if self.kind in (self.Kind.LICENSE, self.Kind.EQUIPMENT):
                raw *= self.periods
        return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def clean(self):
        super().clean()
        errors = {}
        if self.quantity is not None and self.quantity <= 0:
            errors["quantity"] = "La cantidad debe ser mayor que cero."
        if self.periods is not None and self.periods < 1:
            errors["periods"] = "Los períodos deben ser al menos uno."
        for field in ("hours_per_week", "weeks"):
            value = getattr(self, field)
            if value is not None and value <= 0:
                errors[field] = "Debe ser mayor que cero."
        for field in ("hourly_rate", "unit_cost"):
            value = getattr(self, field)
            if value is not None and value < 0:
                errors[field] = "El costo no puede ser negativo."
        is_person = self.kind in (self.Kind.PROFESSIONAL, self.Kind.PROFESSIONAL_TYPE)
        if is_person:
            for key in ("hours_per_week", "weeks", "hourly_rate"):
                if getattr(self, key) is None:
                    errors[key] = "Campo obligatorio para profesionales."
            if self.kind == self.Kind.PROFESSIONAL and self.quantity != Decimal("1"):
                errors["quantity"] = "Un profesional individual debe tener cantidad 1."
            if self.kind == self.Kind.PROFESSIONAL and not self.specialty.strip():
                errors["specialty"] = "Indica la especialidad del profesional."
        elif self.unit_cost is None:
            errors["unit_cost"] = "Campo obligatorio para este tipo de recurso."
        if not is_person and self.periods != 1 and self.kind not in (self.Kind.LICENSE, self.Kind.EQUIPMENT):
            errors["periods"] = "Solo licencias y equipamientos admiten varios periodos."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.project.code} | {self.get_kind_display()} | {self.name}"
