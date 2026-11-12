from core.access import ProjectScopedViewSetMixin

from django.db import transaction
from django.db.models import Q

from rest_framework import serializers, viewsets
from rest_framework.exceptions import ValidationError

from projects.models import Project
from tasks.models import Task

from .models import TaskDependency
from .serializers import TaskDependencySerializer
from .services.dependency_consistency import DependencyConsistencyService


class TaskDependencyViewSet(ProjectScopedViewSetMixin, viewsets.ModelViewSet):
    """
    API REST de dependencias temporales.

    GET     /api/scheduling/dependencies/
    POST    /api/scheduling/dependencies/
    GET     /api/scheduling/dependencies/{id}/
    PUT     /api/scheduling/dependencies/{id}/
    PATCH   /api/scheduling/dependencies/{id}/
    DELETE  /api/scheduling/dependencies/{id}/
    """

    queryset = TaskDependency.objects.select_related(
        "predecessor",
        "successor",
        "predecessor__project",
    ).all()

    serializer_class = TaskDependencySerializer

    @staticmethod
    def parse_positive_id(value, field_name):
        """
        Valida parámetros de consulta numéricos.
        """

        try:
            result = int(value)

            if result <= 0:
                raise ValueError

            return result

        except (TypeError, ValueError):
            raise ValidationError({
                field_name: [
                    "Debe ser un número entero positivo."
                ]
            })

    def get_queryset(self):
        """
        Permite filtrar dependencias por:
        - Proyecto.
        - Tarea predecesora.
        - Tarea sucesora.
        - Tarea participante.
        """

        queryset = super().get_queryset()

        params = self.request.query_params

        project_id = params.get("project")
        predecessor_id = params.get("predecessor")
        successor_id = params.get("successor")
        task_id = params.get("task")

        if project_id:
            project_id = self.parse_positive_id(
                project_id,
                "project",
            )

            queryset = queryset.filter(
                predecessor__project_id=project_id
            )

        if predecessor_id:
            predecessor_id = self.parse_positive_id(
                predecessor_id,
                "predecessor",
            )

            queryset = queryset.filter(
                predecessor_id=predecessor_id
            )

        if successor_id:
            successor_id = self.parse_positive_id(
                successor_id,
                "successor",
            )

            queryset = queryset.filter(
                successor_id=successor_id
            )

        if task_id:
            task_id = self.parse_positive_id(
                task_id,
                "task",
            )

            queryset = queryset.filter(
                Q(predecessor_id=task_id)
                | Q(successor_id=task_id)
            )

        return queryset

    @staticmethod
    def lock_project(project_id):
        """
        Bloquea el registro del proyecto durante
        una operación de escritura.

        Las escrituras coordinadas mediante esta API
        sobre el mismo proyecto se serializan.
        """

        Project.objects.select_for_update().get(
            pk=project_id
        )

    def perform_create(self, serializer):
        """
        Valida y guarda la relación bajo una
        transacción de PostgreSQL.
        """

        predecessor = serializer.validated_data[
            "predecessor"
        ]

        with transaction.atomic():
            self.lock_project(predecessor.project_id)

            # El serializer vuelve a ejecutar full_clean() al guardar.
            dependency = serializer.save()
            # Si se detecta un incumplimiento, se revierte el INSERT.
            DependencyConsistencyService.validate_saved_dependency(dependency)

    def perform_update(self, serializer):
        """
        Protege la actualización de una relación.

        Bloqueamos el proyecto original y obtenemos
        nuevamente la dependencia antes de validar.
        """

        instance = serializer.instance

        with transaction.atomic():
            self.lock_project(
                instance.predecessor.project_id
            )

            # Refrescar la relación dentro de la transacción.
            instance.refresh_from_db()

            # Verificar nuevamente que la relación
            # permanezca en su proyecto original.
            predecessor = serializer.validated_data.get(
                "predecessor",
                instance.predecessor,
            )

            successor = serializer.validated_data.get(
                "successor",
                instance.successor,
            )

            original_project_id = instance.predecessor.project_id

            if (
                predecessor.project_id != original_project_id
                or successor.project_id != original_project_id
            ):
                raise serializers.ValidationError({
                    "non_field_errors": [
                        "No se permite trasladar la dependencia "
                        "a un proyecto diferente."
                    ]
                })

            dependency = serializer.save()
            # Si la relación editada incumple las fechas, revierte el UPDATE.
            DependencyConsistencyService.validate_saved_dependency(dependency)

    def perform_destroy(self, instance):
        """
        Elimina una dependencia de forma transaccional.
        """

        with transaction.atomic():
            self.lock_project(
                instance.predecessor.project_id
            )

            instance.delete()
