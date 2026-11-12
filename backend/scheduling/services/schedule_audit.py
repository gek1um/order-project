"""Auditoría de consistencia del cronograma de order-project.

Fase 3.6.6.1. Solo lectura: no cambia ni guarda modelos.
El resultado diferencia errores de advertencias de datos heredados.
"""

from django.core.exceptions import ValidationError

from projects.models import Project
from tasks.models import Task
from scheduling.models import TaskDependency
from scheduling.services.project_calendar import ProjectCalendarService
from scheduling.services.dependency_planning import DependencyPlanningService


class ScheduleAuditService:
    @staticmethod
    def _issue(code, message, *, task_id=None, dependency_id=None, severity="error"):
        return {
            "severity": severity,
            "code": code,
            "message": message,
            "task_id": task_id,
            "dependency_id": dependency_id,
        }

    @classmethod
    def audit(cls, project_id):
        """Devuelve problemas detectados en tareas y dependencias de un proyecto."""
        project = Project.objects.get(pk=project_id)
        calendar = ProjectCalendarService(project_id)
        tasks = list(Task.objects.filter(project_id=project_id).order_by("id"))
        tasks_by_id = {task.id: task for task in tasks}
        dependencies = list(
            TaskDependency.objects.filter(predecessor__project_id=project_id)
            .order_by("id")
        )
        issues = []

        for task in tasks:
            if not task.start_date or not task.end_date:
                issues.append(cls._issue(
                    "MISSING_DATES", "La actividad no tiene fechas planificadas completas.",
                    task_id=task.id,
                ))
                continue

            if task.end_date < task.start_date:
                issues.append(cls._issue(
                    "REVERSED_DATES", "El término precede al inicio.",
                    task_id=task.id,
                ))
                continue

            if task.start_date < project.start_date or task.end_date > project.end_date:
                issues.append(cls._issue(
                    "OUTSIDE_PROJECT", "La actividad está fuera del período del proyecto.",
                    task_id=task.id,
                ))

            endpoints_work = True
            for field, value in (("start_date", task.start_date), ("end_date", task.end_date)):
                if not calendar.is_working_day(value):
                    endpoints_work = False
                    issues.append(cls._issue(
                        "NON_WORKING_BOUNDARY", f"{field} cae en un día no laborable.",
                        task_id=task.id,
                    ))

            if task.estimated_duration_days is None:
                issues.append(cls._issue(
                    "MISSING_DURATION",
                    "Actividad antigua sin duración estimada; se puede inferir de sus fechas.",
                    task_id=task.id, severity="warning",
                ))
            elif task.estimated_duration_days < 1:
                issues.append(cls._issue(
                    "INVALID_DURATION", "La duración de una actividad debe ser positiva.",
                    task_id=task.id,
                ))
            elif endpoints_work:
                actual_span = calendar.count_working_days(task.start_date, task.end_date)
                if actual_span != task.estimated_duration_days:
                    issues.append(cls._issue(
                        "DURATION_MISMATCH",
                        "La duración estimada no coincide con los días laborables del intervalo.",
                        task_id=task.id,
                    ))

        for dependency in dependencies:
            predecessor = tasks_by_id.get(dependency.predecessor_id)
            successor = tasks_by_id.get(dependency.successor_id)

            if predecessor is None or successor is None:
                issues.append(cls._issue(
                    "INVALID_DEPENDENCY", "La dependencia apunta fuera del proyecto.",
                    dependency_id=dependency.id,
                ))
                continue

            if (not predecessor.start_date or not predecessor.end_date
                    or not successor.start_date or not successor.end_date
                    or successor.end_date < successor.start_date):
                issues.append(cls._issue(
                    "DEPENDENCY_DATES_INVALID", "Faltan fechas válidas para comprobar esta dependencia.",
                    task_id=successor.id, dependency_id=dependency.id,
                ))
                continue

            try:
                duration = DependencyPlanningService._get_duration(successor, calendar)
                required_start = DependencyPlanningService.calculate_constraint(
                    predecessor=predecessor,
                    dependency_type=dependency.dependency_type,
                    lag_days=dependency.lag_days,
                    successor_duration=duration,
                    calendar=calendar,
                )
                if successor.start_date < required_start:
                    issues.append(cls._issue(
                        "DEPENDENCY_VIOLATION",
                        f"La sucesora debería comenzar como mínimo el {required_start.isoformat()}.",
                        task_id=successor.id, dependency_id=dependency.id,
                    ))
            except (ValidationError, ValueError, OverflowError) as exc:
                issues.append(cls._issue(
                    "DEPENDENCY_NOT_EVALUABLE",
                    f"No se pudo evaluar la dependencia: {exc}",
                    task_id=successor.id, dependency_id=dependency.id,
                ))

        errors = [item for item in issues if item["severity"] == "error"]
        warnings = [item for item in issues if item["severity"] == "warning"]
        return {
            "project_id": project.id,
            "valid": not errors,
            "tasks_checked": len(tasks),
            "dependencies_checked": len(dependencies),
            "errors_count": len(errors),
            "warnings_count": len(warnings),
            "issues": issues,
        }
