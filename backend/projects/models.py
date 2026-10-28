
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Project(models.Model):
    """
    Representa un proyecto administrado por la plataforma.
    """

    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planificado"
        IN_PROGRESS = "IN_PROGRESS", "En progreso"
        ON_HOLD = "ON_HOLD", "En pausa"
        COMPLETED = "COMPLETED", "Completado"
        CANCELLED = "CANCELLED", "Cancelado"

    code = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Código",
    )

    name = models.CharField(
        max_length=200,
        verbose_name="Nombre",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Descripción",
    )

    manager_name = models.CharField(
        max_length=150,
        verbose_name="Responsable",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
        verbose_name="Estado",
    )

    start_date = models.DateField(
        verbose_name="Fecha de inicio",
    )

    end_date = models.DateField(
        verbose_name="Fecha de término",
    )

    baseline_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Presupuesto inicial",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización",
    )

    class Meta:
        db_table = "projects"
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="project_valid_dates",
            ),
            models.CheckConstraint(
                condition=Q(baseline_budget__gte=0),
                name="project_nonnegative_budget",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            raise ValidationError({
                "end_date": (
                    "La fecha de término no puede ser "
                    "anterior a la fecha de inicio."
                )
            })

        if (
            self.baseline_budget is not None
            and self.baseline_budget < 0
        ):
            raise ValidationError({
                "baseline_budget": (
                    "El presupuesto no puede ser negativo."
                )
            })

    def __str__(self):
        return f"{self.code} - {self.name}"
