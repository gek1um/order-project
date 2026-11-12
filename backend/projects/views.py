from core.access import ProjectScopedViewSetMixin, IsAdministratorForProjectMutation
from rest_framework.permissions import IsAuthenticated

from django.db import transaction
from django.db.models.deletion import ProtectedError

from rest_framework import status, viewsets
from rest_framework.response import Response

from .models import Project
from .serializers import ProjectSerializer
from scheduling.services.calendar_consistency import ScheduleConsistencyService


class ProjectViewSet(ProjectScopedViewSetMixin, viewsets.ModelViewSet):
    """
    API REST para administración de proyectos.

    GET     /api/projects/
    POST    /api/projects/
    GET     /api/projects/{id}/
    PUT     /api/projects/{id}/
    PATCH   /api/projects/{id}/
    DELETE  /api/projects/{id}/
    """

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, IsAdministratorForProjectMutation]

    def get_queryset(self):
        """
        Permite filtrar proyectos por estado
        y buscar por nombre, código o responsable.
        """

        queryset = super().get_queryset()

        status_filter = self.request.query_params.get(
            "status"
        )

        search = self.request.query_params.get(
            "search"
        )

        if status_filter:
            queryset = queryset.filter(
                status=status_filter
            )

        if search:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
                | Q(manager_name__icontains=search)
            )

        return queryset

    def perform_update(self, serializer):
        """Protege las fechas del proyecto con bloqueo y auditoría transaccional."""
        with transaction.atomic():
            project = Project.objects.select_for_update().get(
                pk=serializer.instance.pk
            )
            # Revalidar dentro del bloqueo: protege reglas del serializer
            # frente a cambios en el estado del proyecto.
            locked_serializer = self.get_serializer(
                project,
                data=serializer.initial_data,
                partial=serializer.partial,
            )
            locked_serializer.is_valid(raise_exception=True)
            before = ScheduleConsistencyService.capture(project.pk)
            updated = locked_serializer.save()
            ScheduleConsistencyService.validate_no_new_errors(
                updated.pk, before
            )

    def destroy(self, request, *args, **kwargs):
        """
        Impide eliminar proyectos que tienen
        tareas asociadas.
        """

        project = self.get_object()

        if project.tasks.exists():
            return Response(
                {
                    "detail": (
                        "No se puede eliminar el proyecto "
                        "porque tiene tareas asociadas."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        try:
            return super().destroy(
                request,
                *args,
                **kwargs,
            )

        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "No se puede eliminar el proyecto "
                        "porque existen registros relacionados."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
