
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from projects.models import Project


class Task(models.Model):
    """
    Representa una actividad perteneciente a un proyecto.
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

    start_date = models.DateField(
        verbose_name="Fecha de inicio",
    )

    end_date = models.DateField(
        verbose_name="Fecha de término",
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
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="task_valid_dates",
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

    def __str__(self):
        return f"{self.project.code} - {self.name}"
