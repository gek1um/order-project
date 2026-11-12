
"""
Motor de planificación individual de tareas.

Fase 3.5.1 - order-project

Responsabilidades:
- Calcular términos planificados.
- Calcular duraciones laborales.
- Reprogramar una tarea de forma segura.
- Respetar el calendario del proyecto.
- Validar límites del proyecto.

No propaga cambios a tareas sucesoras.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from tasks.models import Task

from scheduling.services.project_calendar import (
    ProjectCalendarService,
)


class TaskPlanningService:
    """
    Servicio de cálculo y reprogramación de tareas.
    """

    @staticmethod
    def _validate_duration(duration_days):
        if (
            isinstance(duration_days, bool)
            or not isinstance(duration_days, int)
            or duration_days < 1
        ):
            raise ValidationError({
                "estimated_duration_days": (
                    "La duración debe ser un número "
                    "entero igual o mayor que 1."
                )
            })

    @staticmethod
    def _validate_date(value, field_name):
        if (
            not isinstance(value, date)
            or isinstance(value, __import__(
                "datetime"
            ).datetime)
        ):
            raise ValidationError({
                field_name: (
                    "Se requiere una fecha válida."
                )
            })

    @classmethod
    def calculate_end(
        cls,
        project,
        start_date,
        duration_days,
    ):
        """
        Calcula el término de una tarea usando
        el calendario laboral del proyecto.

        No modifica PostgreSQL.
        """

        cls._validate_date(
            start_date,
            "start_date",
        )

        cls._validate_duration(duration_days)

        calendar = ProjectCalendarService(
            project.id
        )

        if not calendar.is_working_day(start_date):
            raise ValidationError({
                "start_date": (
                    "La fecha de inicio debe ser "
                    "un día laborable."
                )
            })

        if (
            start_date < project.start_date
            or start_date > project.end_date
        ):
            raise ValidationError({
                "start_date": (
                    "El inicio debe estar dentro "
                    "del período del proyecto."
                )
            })

        try:
            end_date = calendar.calculate_end_date(
                start_date,
                duration_days,
            )
        except (ValueError, OverflowError) as exc:
            raise ValidationError({
                "estimated_duration_days": str(exc)
            }) from exc

        if end_date > project.end_date:
            raise ValidationError({
                "end_date": (
                    "El término calculado supera "
                    "la fecha final del proyecto."
                )
            })

        return end_date

    @classmethod
    def calculate_duration(
        cls,
        project,
        start_date,
        end_date,
    ):
        """
        Calcula los días laborables de una
        actividad entre inicio y término.

        Ambos extremos deben ser laborables.
        """

        cls._validate_date(
            start_date,
            "start_date",
        )

        cls._validate_date(
            end_date,
            "end_date",
        )

        if end_date < start_date:
            raise ValidationError({
                "end_date": (
                    "El término no puede ser "
                    "anterior al inicio."
                )
            })

        if (
            start_date < project.start_date
            or end_date > project.end_date
        ):
            raise ValidationError({
                "non_field_errors": (
                    "La programación debe estar "
                    "dentro del período del proyecto."
                )
            })

        calendar = ProjectCalendarService(
            project.id
        )

        if not calendar.is_working_day(start_date):
            raise ValidationError({
                "start_date": (
                    "El inicio debe ser laborable."
                )
            })

        if not calendar.is_working_day(end_date):
            raise ValidationError({
                "end_date": (
                    "El término debe ser laborable."
                )
            })

        duration = calendar.count_working_days(
            start_date,
            end_date,
        )

        if duration < 1:
            raise ValidationError({
                "estimated_duration_days": (
                    "La duración calculada "
                    "debe ser al menos 1."
                )
            })

        return duration

    @classmethod
    def preview(
        cls,
        project,
        start_date,
        duration_days,
    ):
        """
        Devuelve una vista previa de la
        programación sin guardar cambios.
        """

        end_date = cls.calculate_end(
            project,
            start_date,
            duration_days,
        )

        return {
            "project_id": project.id,
            "start_date": start_date,
            "end_date": end_date,
            "estimated_duration_days": duration_days,
        }

    @classmethod
    @transaction.atomic
    def reschedule(
        cls,
        task_id,
        start_date,
        duration_days,
    ):
        """
        Reprograma una tarea existente.

        Protege la actualización mediante
        una transacción y un bloqueo de fila.

        No modifica las tareas dependientes;
        eso se implementará en 3.5.3.
        """

        task = (
            Task.objects
            .select_related("project")
            .select_for_update()
            .get(pk=task_id)
        )

        result = cls.preview(
            task.project,
            start_date,
            duration_days,
        )

        task.start_date = result["start_date"]
        task.end_date = result["end_date"]

        task.estimated_duration_days = (
            result["estimated_duration_days"]
        )

        task.full_clean()

        task.save(
            update_fields=[
                "start_date",
                "end_date",
                "estimated_duration_days",
                "updated_at",
            ]
        )

        return task
