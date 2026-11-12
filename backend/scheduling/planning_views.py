
"""
API REST de planificación - order-project.

Fase 3.5.4

Endpoints:
POST tasks/{id}/preview/
POST tasks/{id}/reschedule/
GET  projects/{id}/schedule/
"""

from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)

from django.shortcuts import get_object_or_404
from core.access import project_or_404, task_or_404

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.models import Project
from tasks.models import Task
from scheduling.models import TaskDependency

from scheduling.planning_serializers import (
    RescheduleRequestSerializer,
    ScheduleResultSerializer,
)

from scheduling.services.project_calendar import (
    ProjectCalendarService,
)

from scheduling.services.schedule_propagation import (
    SchedulePropagationService,
)


def convert_validation_error(exc):
    """
    Convierte errores de validación de Django
    en errores HTTP 400 de Django REST Framework.
    """

    if hasattr(exc, "message_dict"):
        return serializers.ValidationError(
            exc.message_dict
        )

    return serializers.ValidationError({
        "non_field_errors": exc.messages
    })


class BaseRescheduleView(APIView):
    """
    Lógica compartida entre simulación
    y confirmación de reprogramaciones.
    """

    commit_changes = False

    def post(self, request, task_id):
        task_or_404(request.user, task_id)

        serializer = RescheduleRequestSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        try:
            result = (
                SchedulePropagationService.propagate(
                    task_id=task_id,
                    start_date=data["start_date"],
                    duration_days=data["duration_days"],
                    commit=self.commit_changes,
                )
            )

        except DjangoValidationError as exc:
            raise convert_validation_error(
                exc
            ) from exc

        except Task.DoesNotExist:
            # Protege también ante una eliminación
            # concurrente entre la consulta inicial
            # y el inicio de la transacción.
            from rest_framework.exceptions import NotFound

            raise NotFound(
                "La actividad no existe."
            )

        output = ScheduleResultSerializer(
            result
        )

        return Response(
            output.data,
            status=status.HTTP_200_OK,
        )


class TaskSchedulePreviewView(
    BaseRescheduleView
):
    """
    Simula una reprogramación.

    No escribe cambios en PostgreSQL.
    """

    commit_changes = False


class TaskScheduleRescheduleView(
    BaseRescheduleView
):
    """
    Aplica una reprogramación.

    El servicio utiliza una transacción
    y protege todas las tareas involucradas.
    """

    commit_changes = True


class ProjectScheduleView(APIView):
    """
    Consulta el cronograma de un proyecto.

    Devuelve:
    - Información del proyecto.
    - Calendario efectivo.
    - Actividades planificadas.
    - Dependencias registradas.
    """

    def get(self, request, project_id):
        project = project_or_404(request.user, project_id)

        calendar = ProjectCalendarService(
            project.id
        )

        tasks = list(
            Task.objects
            .filter(project_id=project.id)
            .order_by(
                "position",
                "id",
            )
            .values(
                "id",
                "name",
                "description",
                "status",
                "start_date",
                "end_date",
                "actual_start_date",
                "actual_end_date",
                "estimated_duration_days",
                "actual_duration_days",
                "progress_percent",
                "position",
            )
        )

        dependencies = list(
            TaskDependency.objects
            .filter(
                predecessor__project_id=project.id
            )
            .order_by("id")
            .values(
                "id",
                "predecessor_id",
                "successor_id",
                "dependency_type",
                "lag_days",
            )
        )

        return Response({
            "project": {
                "id": project.id,
                "code": project.code,
                "name": project.name,
                "status": project.status,
                "start_date": project.start_date,
                "end_date": project.end_date,
            },
            "calendar": {
                "source": calendar.source,
                "calendar_id": (
                    calendar.calendar.id
                    if calendar.calendar
                    else None
                ),
                "working_weekdays": sorted(
                    calendar.working_weekdays
                ),
                "exceptions": [
                    {
                        "date": day,
                        "is_working": is_working,
                    }
                    for day, is_working in sorted(
                        calendar.exceptions.items()
                    )
                ],
            },
            "tasks_count": len(tasks),
            "dependencies_count": len(dependencies),
            "tasks": tasks,
            "dependencies": dependencies,
        })
