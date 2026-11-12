
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from projects.models import Project


class Task(models.Model):
    """
    Representa una actividad perteneciente a un proyecto.

    Incluye planificación vigente, fechas de ejecución
    real, duraciones y porcentaje de avance.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        IN_PROGRESS = "IN_PROGRESS", "En progreso"
        COMPLETED = "COMPLETED", "Completada"
        CANCELLED = "CANCELLED", "Cancelada"

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="tasks",
        verbose_name="Proyecto",
    )

    name = models.CharField(
        max_length=200,
        verbose_name="Nombre",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Descripción",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Estado",
    )

    # =========================================
    # FECHAS PLANIFICADAS VIGENTES
    # =========================================

    start_date = models.DateField(
        verbose_name="Fecha de inicio planificada",
    )

    end_date = models.DateField(
        verbose_name="Fecha de término planificada",
    )

    # =========================================
    # FECHAS REALES
    # =========================================

    actual_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha real de inicio",
    )

    actual_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha real de término",
    )

    # =========================================
    # DURACIONES
    # =========================================

    estimated_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Duración estimada en días laborables",
    )

    actual_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Duración real en días laborables",
    )

    # =========================================
    # AVANCE DE LA ACTIVIDAD
    # =========================================

    progress_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Porcentaje de avance",
    )

    position = models.PositiveIntegerField(
        default=0,
        verbose_name="Orden de visualización",
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
        db_table = "tasks"
        verbose_name = "Tarea"
        verbose_name_plural = "Tareas"
        ordering = ["position", "id"]

        constraints = [
            # Validación existente.
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="task_valid_dates",
            ),

            # Avance permitido: 0 a 100 %.
            models.CheckConstraint(
                condition=(
                    Q(progress_percent__gte=0)
                    & Q(progress_percent__lte=100)
                ),
                name="task_progress_valid_range",
            ),

            # Si hay término real, debe existir inicio real.
            models.CheckConstraint(
                condition=(
                    Q(actual_end_date__isnull=True)
                    | Q(actual_start_date__isnull=False)
                ),
                name="task_actual_end_requires_start",
            ),

            # Las fechas reales deben estar ordenadas.
            models.CheckConstraint(
                condition=(
                    Q(actual_end_date__isnull=True)
                    | Q(actual_start_date__isnull=True)
                    | Q(
                        actual_end_date__gte=F(
                            "actual_start_date"
                        )
                    )
                ),
                name="task_valid_actual_dates",
            ),
        ]

    def clean(self):
        """
        Comprueba la coherencia de los campos
        temporales de la actividad.
        """

        super().clean()

        errors = {}

        # -------------------------------------
        # FECHAS PLANIFICADAS
        # -------------------------------------

        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            errors["end_date"] = (
                "La fecha de término no puede ser "
                "anterior a la fecha de inicio."
            )

        # -------------------------------------
        # FECHAS REALES
        # -------------------------------------

        if self.actual_end_date and not self.actual_start_date:
            errors["actual_start_date"] = (
                "Debes registrar la fecha real de inicio "
                "antes de registrar el término real."
            )

        if (
            self.actual_start_date
            and self.actual_end_date
            and self.actual_end_date < self.actual_start_date
        ):
            errors["actual_end_date"] = (
                "La fecha real de término no puede "
                "ser anterior al inicio real."
            )

        # -------------------------------------
        # DURACIONES
        # -------------------------------------

        if (
            self.estimated_duration_days is not None
            and self.estimated_duration_days < 0
        ):
            errors["estimated_duration_days"] = (
                "La duración estimada no puede ser negativa."
            )

        if (
            self.actual_duration_days is not None
            and self.actual_duration_days < 0
        ):
            errors["actual_duration_days"] = (
                "La duración real no puede ser negativa."
            )

        # -------------------------------------
        # PORCENTAJE DE AVANCE
        # -------------------------------------

        if self.progress_percent is not None:
            if not (
                Decimal("0.00")
                <= self.progress_percent
                <= Decimal("100.00")
            ):
                errors["progress_percent"] = (
                    "El avance debe encontrarse "
                    "entre 0 y 100 %."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.project.code} - {self.name}"
