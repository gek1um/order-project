
from rest_framework import serializers

from projects.models import Project
from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    """
    Convierte tareas a JSON y valida sus datos
    antes de guardar cambios en PostgreSQL.
    """

    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all()
    )

    project_code = serializers.CharField(
        source="project.code",
        read_only=True,
    )

    project_name = serializers.CharField(
        source="project.name",
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Task

        fields = [
            "id",
            "project",
            "project_code",
            "project_name",
            "name",
            "description",
            "status",
            "status_display",
            "start_date",
            "end_date",
            "position",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "project_code",
            "project_name",
            "status_display",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        """
        Valida:
        - Relación con proyecto.
        - Fechas coherentes.
        - Fechas dentro del proyecto.
        - Imposibilidad de reasignar una tarea.
        """

        instance = self.instance

        project = attrs.get(
            "project",
            instance.project if instance else None,
        )

        start_date = attrs.get(
            "start_date",
            instance.start_date if instance else None,
        )

        end_date = attrs.get(
            "end_date",
            instance.end_date if instance else None,
        )

        errors = {}

        if instance and "project" in attrs:
            if project.pk != instance.project_id:
                errors["project"] = (
                    "No se permite cambiar el proyecto "
                    "de una tarea existente."
                )

        if start_date and end_date:
            if end_date < start_date:
                errors["end_date"] = (
                    "La fecha de término no puede ser "
                    "anterior a la fecha de inicio."
                )

        if project and start_date and end_date:
            if start_date < project.start_date:
                errors["start_date"] = (
                    "La tarea no puede comenzar antes "
                    "del inicio del proyecto."
                )

            if end_date > project.end_date:
                errors["end_date"] = (
                    "La tarea no puede finalizar después "
                    "del término del proyecto."
                )

        if errors:
            raise serializers.ValidationError(errors)

        return attrs
