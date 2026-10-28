
from django.db.models import Q

from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from .models import Task
from .serializers import TaskSerializer


class TaskViewSet(viewsets.ModelViewSet):
    """
    API REST de administración de tareas.

    GET     /api/tasks/
    POST    /api/tasks/
    GET     /api/tasks/{id}/
    PUT     /api/tasks/{id}/
    PATCH   /api/tasks/{id}/
    DELETE  /api/tasks/{id}/
    """

    queryset = Task.objects.select_related(
        "project"
    ).all()

    serializer_class = TaskSerializer

    def get_queryset(self):
        """
        Permite filtrar, buscar y ordenar tareas.
        """

        queryset = super().get_queryset()

        project_id = self.request.query_params.get(
            "project"
        )

        status_filter = self.request.query_params.get(
            "status"
        )

        search = self.request.query_params.get(
            "search"
        )

        ordering = self.request.query_params.get(
            "ordering"
        )

        if project_id:
            try:
                project_id = int(project_id)

                if project_id <= 0:
                    raise ValueError

            except (TypeError, ValueError):
                raise ValidationError({
                    "project": (
                        "El ID del proyecto debe ser "
                        "un número entero positivo."
                    )
                })

            queryset = queryset.filter(
                project_id=project_id
            )

        if status_filter:
            valid_statuses = [
                value
                for value, _ in Task.Status.choices
            ]

            if status_filter not in valid_statuses:
                raise ValidationError({
                    "status": "Estado de tarea no válido."
                })

            queryset = queryset.filter(
                status=status_filter
            )

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(project__name__icontains=search)
                | Q(project__code__icontains=search)
            )

        allowed_ordering = {
            "position",
            "-position",
            "start_date",
            "-start_date",
            "end_date",
            "-end_date",
            "created_at",
            "-created_at",
            "name",
            "-name",
        }

        if ordering:
            if ordering not in allowed_ordering:
                raise ValidationError({
                    "ordering": (
                        "El criterio de ordenamiento "
                        "no está permitido."
                    )
                })

            queryset = queryset.order_by(
                ordering,
                "id",
            )

        return queryset
