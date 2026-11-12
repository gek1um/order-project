
"""
Motor de dependencias temporales - order-project.

Fase 3.5.2

Calcula la programación más temprana de una
actividad sucesora considerando:

- FS, SS, FF y SF.
- Desfases positivos y negativos.
- Calendario laboral del proyecto.
- Múltiples predecesoras.
- Duraciones estimadas.

No guarda cambios en PostgreSQL.
No propaga fechas a otras actividades.
"""

from datetime import date

from django.core.exceptions import ValidationError

from scheduling.models import TaskDependency
from scheduling.services.project_calendar import (
    ProjectCalendarService,
)
from tasks.models import Task


class DependencyPlanningService:

    @staticmethod
    def _validate_duration(duration):
        if (
            isinstance(duration, bool)
            or not isinstance(duration, int)
            or duration < 1
        ):
            raise ValidationError({
                "estimated_duration_days": (
                    "La duración de una actividad "
                    "debe ser un entero mayor o "
                    "igual que 1."
                )
            })

    @staticmethod
    def _get_duration(task, calendar):
        """
        Utiliza la duración estimada cuando existe.

        Para actividades antiguas que todavía no
        tienen duración registrada, la calcula
        mediante sus fechas planificadas.
        """

        duration = task.estimated_duration_days

        if duration is not None:
            DependencyPlanningService._validate_duration(
                duration
            )
            return duration

        if not task.start_date or not task.end_date:
            raise ValidationError({
                "estimated_duration_days": (
                    "La actividad necesita duración "
                    "estimada o fechas planificadas."
                )
            })

        if (
            not calendar.is_working_day(task.start_date)
            or not calendar.is_working_day(task.end_date)
        ):
            raise ValidationError({
                "non_field_errors": (
                    "Las fechas de la actividad "
                    "deben ser laborables para "
                    "inferir su duración."
                )
            })

        if task.end_date < task.start_date:
            raise ValidationError({
                "end_date": (
                    "El término es anterior al inicio."
                )
            })

        return calendar.count_working_days(
            task.start_date,
            task.end_date,
        )

    @staticmethod
    def calculate_constraint(
        predecessor,
        dependency_type,
        lag_days,
        successor_duration,
        calendar,
    ):
        """
        Calcula la fecha mínima de inicio de B.

        El resultado es una restricción de inicio
        que el sucesor deberá respetar.

        Reglas:
        FS: siguiente hábil tras fin de A + lag
        SS: inicio de A + lag
        FF: fin de A + lag, convertido a inicio B
        SF: inicio de A + lag, convertido a inicio B

        En FF/SF se resta (duración B - 1) días
        laborables para calcular el inicio mínimo.
        """

        DependencyPlanningService._validate_duration(
            successor_duration
        )

        if (
            isinstance(lag_days, bool)
            or not isinstance(lag_days, int)
        ):
            raise ValidationError({
                "lag_days": (
                    "El desfase debe ser un entero."
                )
            })

        valid_types = {
            item[0]
            for item in TaskDependency.DependencyType.choices
        }

        if dependency_type not in valid_types:
            raise ValidationError({
                "dependency_type": (
                    "Tipo de dependencia inválido."
                )
            })

        if (
            not predecessor.start_date
            or not predecessor.end_date
        ):
            raise ValidationError({
                "non_field_errors": (
                    "La predecesora debe tener "
                    "fechas planificadas."
                )
            })

        if (
            not isinstance(predecessor.start_date, date)
            or not isinstance(predecessor.end_date, date)
        ):
            raise ValidationError({
                "non_field_errors": (
                    "Las fechas de la predecesora "
                    "deben ser válidas."
                )
            })

        if (
            not calendar.is_working_day(
                predecessor.start_date
            )
            or not calendar.is_working_day(
                predecessor.end_date
            )
        ):
            raise ValidationError({
                "non_field_errors": (
                    "La predecesora debe comenzar "
                    "y terminar en días laborables."
                )
            })

        if predecessor.end_date < predecessor.start_date:
            raise ValidationError({
                "end_date": (
                    "La predecesora tiene fechas "
                    "planificadas inválidas."
                )
            })

        if dependency_type == "FS":
            # Con desfase cero, B comienza el
            # siguiente día laborable tras A.
            base_date = calendar.next_working_day(
                predecessor.end_date,
                include_today=False,
            )

            return calendar.shift_working_days(
                base_date,
                lag_days,
            )

        if dependency_type == "SS":
            # Inicio B >= inicio A + desfase.
            return calendar.shift_working_days(
                predecessor.start_date,
                lag_days,
            )

        if dependency_type == "FF":
            # Fin B >= fin A + desfase.
            target_end = calendar.shift_working_days(
                predecessor.end_date,
                lag_days,
            )

            return calendar.shift_working_days(
                target_end,
                -(successor_duration - 1),
            )

        # SF: fin B >= inicio A + desfase.
        target_end = calendar.shift_working_days(
            predecessor.start_date,
            lag_days,
        )

        return calendar.shift_working_days(
            target_end,
            -(successor_duration - 1),
        )

    @classmethod
    def preview_successor(cls, successor_id):
        """
        Calcula la programación más temprana que
        satisface todas las dependencias entrantes.

        No modifica registros.

        Retorna fechas y detalle de restricciones.
        """

        successor = (
            Task.objects
            .select_related("project")
            .get(pk=successor_id)
        )

        calendar = ProjectCalendarService(
            successor.project_id
        )

        dependencies = list(
            TaskDependency.objects
            .filter(successor_id=successor_id)
            .select_related("predecessor")
            .order_by("id")
        )

        if not dependencies:
            raise ValidationError({
                "dependencies": (
                    "La actividad no tiene "
                    "predecesoras configuradas."
                )
            })

        duration = cls._get_duration(
            successor,
            calendar,
        )

        constraints = []

        for dependency in dependencies:
            predecessor = dependency.predecessor

            if predecessor.project_id != successor.project_id:
                raise ValidationError({
                    "dependencies": (
                        "La dependencia conecta "
                        "actividades de proyectos "
                        "diferentes."
                    )
                })

            required_start = cls.calculate_constraint(
                predecessor=predecessor,
                dependency_type=dependency.dependency_type,
                lag_days=dependency.lag_days,
                successor_duration=duration,
                calendar=calendar,
            )

            constraints.append({
                "dependency_id": dependency.id,
                "predecessor_id": predecessor.id,
                "dependency_type": dependency.dependency_type,
                "lag_days": dependency.lag_days,
                "required_start": required_start,
            })

        # Con varias predecesoras, elegir la fecha
        # de inicio mínima que satisface todas.
        earliest_start = max(
            item["required_start"]
            for item in constraints
        )

        earliest_end = calendar.calculate_end_date(
            earliest_start,
            duration,
        )

        project = successor.project

        if (
            earliest_start < project.start_date
            or earliest_end > project.end_date
        ):
            raise ValidationError({
                "non_field_errors": (
                    "La programación calculada "
                    "queda fuera de las fechas "
                    "permitidas del proyecto."
                )
            })

        return {
            "task_id": successor.id,
            "project_id": project.id,
            "estimated_duration_days": duration,
            "start_date": earliest_start,
            "end_date": earliest_end,
            "dependencies_count": len(dependencies),
            "constraints": constraints,
        }
