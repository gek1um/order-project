
"""
order-project - Fase 3.5.3

Motor de propagación automática del cronograma.

Características:
- Reprograma una tarea origen.
- Recalcula todas sus sucesoras alcanzables.
- Soporta FS, SS, FF, SF y desfases.
- Respeta calendarios por proyecto.
- Respeta múltiples predecesoras.
- Mantiene las fechas existentes si ya cumplen.
- Protege tareas iniciadas o finalizadas.
- Guarda los cambios en una transacción.
- Permite simulaciones sin guardar.

La integración con la API REST corresponde
a la Fase 3.5.4.
"""

from collections import deque
from copy import copy
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from projects.models import Project
from tasks.models import Task
from scheduling.models import TaskDependency

from scheduling.services.project_calendar import (
    ProjectCalendarService,
)
from scheduling.services.task_planning import (
    TaskPlanningService,
)
from scheduling.services.dependency_planning import (
    DependencyPlanningService,
)


class SchedulePropagationService:
    """
    Propaga modificaciones de programación
    a las tareas sucesoras del mismo proyecto.
    """

    @staticmethod
    def _is_locked_task(task):
        """
        Una actividad con ejecución registrada
        no debe ser reprogramada automáticamente.
        """

        locked_statuses = {
            Task.Status.IN_PROGRESS,
            Task.Status.COMPLETED,
            Task.Status.CANCELLED,
        }

        return (
            task.status in locked_statuses
            or task.actual_start_date is not None
            or task.actual_end_date is not None
            or task.progress_percent > Decimal("0")
        )

    @staticmethod
    def _get_reachable_ids(root_id, outgoing):
        """
        Encuentra todas las sucesoras de la
        tarea origen mediante búsqueda en anchura.
        """

        reachable = {root_id}
        pending = deque([root_id])

        while pending:
            task_id = pending.popleft()

            for successor_id in outgoing.get(
                task_id, set()
            ):
                if successor_id not in reachable:
                    reachable.add(successor_id)
                    pending.append(successor_id)

        return reachable

    @staticmethod
    def _topological_order(
        reachable,
        dependencies,
    ):
        """
        Ordena las actividades afectadas de
        modo que cada predecesora afectada
        sea procesada antes que su sucesora.

        Protege también contra ciclos residuales
        que pudieran existir en la base de datos.
        """

        indegree = {
            task_id: 0
            for task_id in reachable
        }

        outgoing = {
            task_id: set()
            for task_id in reachable
        }

        for dependency in dependencies:
            predecessor_id = (
                dependency.predecessor_id
            )
            successor_id = dependency.successor_id

            if (
                predecessor_id in reachable
                and successor_id in reachable
                and successor_id not in outgoing[
                    predecessor_id
                ]
            ):
                outgoing[
                    predecessor_id
                ].add(successor_id)

                indegree[successor_id] += 1

        ready = deque(
            sorted(
                task_id
                for task_id, degree in indegree.items()
                if degree == 0
            )
        )

        result = []

        while ready:
            current = ready.popleft()
            result.append(current)

            for successor_id in sorted(
                outgoing[current]
            ):
                indegree[successor_id] -= 1

                if indegree[successor_id] == 0:
                    ready.append(successor_id)

        if len(result) != len(reachable):
            raise ValidationError({
                "dependencies": (
                    "El cronograma contiene un "
                    "ciclo de dependencias."
                )
            })

        return result

    @staticmethod
    def _validate_project_dates(
        task,
        project,
    ):
        """
        Verifica que la planificación esté
        dentro del período del proyecto.
        """

        if (
            task.start_date < project.start_date
            or task.end_date > project.end_date
            or task.end_date < task.start_date
        ):
            raise ValidationError({
                "non_field_errors": (
                    f"La actividad {task.id} "
                    "queda fuera del período "
                    "permitido del proyecto."
                )
            })

    @classmethod
    @transaction.atomic
    def propagate(
        cls,
        task_id,
        start_date,
        duration_days,
        commit=True,
    ):
        """
        Reprograma la tarea de origen y propaga
        los cambios a sus sucesoras.

        commit=True:
            Valida y guarda los cambios.

        commit=False:
            Calcula una simulación sin guardar.

        Devuelve un diccionario con el resultado.
        """

        # -------------------------------------
        # 1. IDENTIFICAR EL PROYECTO
        # -------------------------------------

        root_reference = Task.objects.only(
            "id",
            "project_id",
        ).get(pk=task_id)

        # Todos los cambios de planificación de
        # este servicio bloquean primero el proyecto.
        project = (
            Project.objects
            .select_for_update()
            .get(pk=root_reference.project_id)
        )

        # -------------------------------------
        # 2. BLOQUEAR Y CARGAR LAS TAREAS
        # -------------------------------------

        tasks = list(
            Task.objects
            .filter(project_id=project.id)
            .select_for_update()
            .order_by("id")
        )

        tasks_by_id = {
            task.id: task
            for task in tasks
        }

        if task_id not in tasks_by_id:
            raise ValidationError({
                "task": (
                    "La actividad no pertenece "
                    "al proyecto esperado."
                )
            })

        # -------------------------------------
        # 3. CONSULTAR DEPENDENCIAS
        # -------------------------------------

        dependencies = list(
            TaskDependency.objects
            .filter(
                predecessor__project_id=project.id
            )
            .order_by("id")
        )

        outgoing = {}
        incoming = {}

        for dependency in dependencies:
            predecessor_id = (
                dependency.predecessor_id
            )
            successor_id = dependency.successor_id

            if (
                predecessor_id not in tasks_by_id
                or successor_id not in tasks_by_id
            ):
                raise ValidationError({
                    "dependencies": (
                        "Existen dependencias "
                        "entre proyectos distintos "
                        "o actividades inexistentes."
                    )
                })

            outgoing.setdefault(
                predecessor_id, set()
            ).add(successor_id)

            incoming.setdefault(
                successor_id, []
            ).append(dependency)

        # -------------------------------------
        # 4. DETERMINAR ACTIVIDADES AFECTADAS
        # -------------------------------------

        reachable = cls._get_reachable_ids(
            task_id,
            outgoing,
        )

        ordered_ids = cls._topological_order(
            reachable,
            dependencies,
        )

        # Guardamos las fechas originales
        # para comparar y para el resultado.
        originals = {
            current_id: {
                "start_date": tasks_by_id[
                    current_id
                ].start_date,
                "end_date": tasks_by_id[
                    current_id
                ].end_date,
                "estimated_duration_days": (
                    tasks_by_id[
                        current_id
                    ].estimated_duration_days
                ),
            }
            for current_id in reachable
        }

        # -------------------------------------
        # 5. CALENDARIO DEL PROYECTO
        # -------------------------------------

        calendar = ProjectCalendarService(
            project.id
        )

        # -------------------------------------
        # 6. REPROGRAMAR ACTIVIDAD ORIGEN
        # -------------------------------------

        root = tasks_by_id[task_id]

        new_root_end = (
            TaskPlanningService.calculate_end(
                project,
                start_date,
                duration_days,
            )
        )

        root_dates_changed = (
            root.start_date != start_date
            or root.end_date != new_root_end
        )

        if (
            root_dates_changed
            and cls._is_locked_task(root)
        ):
            raise ValidationError({
                "task": (
                    "No se permite reprogramar "
                    "una actividad que ya inició, "
                    "finalizó o registra avance."
                )
            })

        root.start_date = start_date
        root.end_date = new_root_end

        root.estimated_duration_days = (
            duration_days
        )

        cls._validate_project_dates(
            root,
            project,
        )

        # -------------------------------------
        # 7. PROPAGAR A LAS SUCESORAS
        # -------------------------------------

        for current_id in ordered_ids:
            if current_id == task_id:
                continue

            successor = tasks_by_id[current_id]

            duration = (
                DependencyPlanningService
                ._get_duration(
                    successor,
                    calendar,
                )
            )

            constraints = []

            for dependency in incoming.get(
                current_id, []
            ):
                predecessor = tasks_by_id[
                    dependency.predecessor_id
                ]

                required_start = (
                    DependencyPlanningService
                    .calculate_constraint(
                        predecessor=predecessor,
                        dependency_type=(
                            dependency.dependency_type
                        ),
                        lag_days=dependency.lag_days,
                        successor_duration=duration,
                        calendar=calendar,
                    )
                )

                constraints.append(
                    required_start
                )

            if not constraints:
                continue

            minimum_start = max(constraints)

            # La propagación solo empuja fechas
            # hacia adelante. No adelanta tareas
            # que ya cumplen las dependencias.
            planned_start = successor.start_date

            if planned_start < minimum_start:
                new_start = minimum_start
            else:
                new_start = planned_start

            # Si la fecha conservada resulta
            # no laborable, buscar la siguiente.
            if not calendar.is_working_day(
                new_start
            ):
                new_start = (
                    calendar.next_working_day(
                        new_start
                    )
                )

            new_end = (
                calendar.calculate_end_date(
                    new_start,
                    duration,
                )
            )

            dates_changed = (
                successor.start_date != new_start
                or successor.end_date != new_end
            )

            if (
                dates_changed
                and cls._is_locked_task(successor)
            ):
                raise ValidationError({
                    "task": (
                        f"La actividad {successor.id} "
                        "ya registra ejecución y "
                        "necesita una reprogramación. "
                        "No se aplicaron cambios."
                    )
                })

            successor.start_date = new_start
            successor.end_date = new_end

            # Normalizamos también la duración
            # en actividades antiguas cuando
            # era posible inferirla.
            successor.estimated_duration_days = (
                duration
            )

            cls._validate_project_dates(
                successor,
                project,
            )

        # -------------------------------------
        # 8. VALIDAR TODAS LAS MODIFICACIONES
        # -------------------------------------

        changes = []

        for current_id in ordered_ids:
            task = tasks_by_id[current_id]
            previous = originals[current_id]

            has_changed = (
                previous["start_date"]
                != task.start_date
                or previous["end_date"]
                != task.end_date
                or previous[
                    "estimated_duration_days"
                ] != task.estimated_duration_days
            )

            if not has_changed:
                continue

            # Utilizamos la copia para preservar
            # correctamente el estado del modelo
            # durante la validación Django.
            candidate = copy(task)
            candidate.full_clean()

            changes.append({
                "task_id": task.id,
                "name": task.name,
                "old_start_date": (
                    previous["start_date"]
                ),
                "old_end_date": (
                    previous["end_date"]
                ),
                "new_start_date": task.start_date,
                "new_end_date": task.end_date,
                "estimated_duration_days": (
                    task.estimated_duration_days
                ),
                "is_origin": task.id == task_id,
            })

        # -------------------------------------
        # 9. GUARDAR DE FORMA ATÓMICA
        # -------------------------------------

        if commit:
            for change in changes:
                task = tasks_by_id[
                    change["task_id"]
                ]

                task.save(
                    update_fields=[
                        "start_date",
                        "end_date",
                        "estimated_duration_days",
                        "updated_at",
                    ]
                )

        # -------------------------------------
        # 10. RESULTADO
        # -------------------------------------

        return {
            "project_id": project.id,
            "origin_task_id": task_id,
            "committed": bool(commit),
            "affected_tasks": len(reachable),
            "updated_tasks": len(changes),
            "changes": changes,
        }
