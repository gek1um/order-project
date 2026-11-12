from core.access import ScopedRelationsMixin

from copy import copy

from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)

from rest_framework import serializers

from projects.models import Project
from .models import Task


class TaskSerializer(ScopedRelationsMixin, serializers.ModelSerializer):
    """
    Serializer de actividades de order-project.

    Funcionalidades:
    - Crear tareas.
    - Consultar tareas.
    - Editar información general.
    - Gestionar fechas reales.
    - Gestionar avance porcentual.
    - Validar fechas y proyecto.
    - Proteger la planificación temporal.

    Las fechas planificadas de una tarea
    existente solo pueden modificarse
    mediante SchedulePropagationService.
    """

    PLANNING_FIELDS = (
        "start_date",
        "end_date",
        "estimated_duration_days",
    )

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
            "actual_start_date",
            "actual_end_date",
            "estimated_duration_days",
            "actual_duration_days",
            "progress_percent",
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

    # =========================================
    # VALIDACIONES DEL MODELO
    # =========================================

    @staticmethod
    def validate_model(instance):
        """
        Ejecuta full_clean() del modelo.

        Convierte los errores de Django en
        errores compatibles con DRF.
        """

        try:
            instance.full_clean()

        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise serializers.ValidationError(
                    exc.message_dict
                ) from exc

            raise serializers.ValidationError({
                "non_field_errors": exc.messages
            }) from exc

    # =========================================
    # PROTECCIÓN DE PLANIFICACIÓN
    # =========================================

    def validate_planning_changes(
        self,
        current,
        attrs,
    ):
        """
        Impide modificar directamente la
        programación de una tarea existente.

        Permite enviar un campo si su valor
        coincide con el que ya está guardado.

        De esta manera, las actualizaciones
        PUT que incluyen fechas sin cambiarlas
        siguen siendo compatibles.
        """

        if current is None:
            # La creación inicial de tareas
            # sigue permitiendo fechas.
            return

        errors = {}

        for field in self.PLANNING_FIELDS:
            if field not in attrs:
                continue

            current_value = getattr(
                current,
                field,
            )

            requested_value = attrs[field]

            if requested_value != current_value:
                errors[field] = [
                    "Este campo no puede modificarse "
                    "desde el CRUD de tareas. "
                    "Utiliza el endpoint de "
                    "reprogramación de Scheduling."
                ]

        if errors:
            raise serializers.ValidationError(
                errors
            )

    # =========================================
    # VALIDACIÓN DE DATOS
    # =========================================

    def validate(self, attrs):
        """
        Valida el estado final de la tarea.

        En PATCH conserva los campos que
        no fueron enviados.

        Protege las fechas planificadas,
        pero permite modificar información
        general y datos reales.
        """

        current = self.instance

        # -------------------------------------
        # PROTEGER LA PLANIFICACIÓN
        # -------------------------------------

        self.validate_planning_changes(
            current,
            attrs,
        )

        # -------------------------------------
        # VALIDAR PROYECTO
        # -------------------------------------

        project = attrs.get(
            "project",
            current.project if current else None,
        )

        if current and project:
            if project.pk != current.project_id:
                raise serializers.ValidationError({
                    "project": [
                        "No se permite reasignar "
                        "una tarea a otro proyecto."
                    ]
                })

        # -------------------------------------
        # FECHAS PLANIFICADAS
        # -------------------------------------

        start_date = attrs.get(
            "start_date",
            current.start_date if current else None,
        )

        end_date = attrs.get(
            "end_date",
            current.end_date if current else None,
        )

        if start_date and end_date:
            if end_date < start_date:
                raise serializers.ValidationError({
                    "end_date": [
                        "La fecha de término no puede "
                        "ser anterior al inicio."
                    ]
                })

        # -------------------------------------
        # LÍMITES DEL PROYECTO
        # -------------------------------------

        if project and start_date and end_date:
            if (
                start_date < project.start_date
                or end_date > project.end_date
            ):
                raise serializers.ValidationError({
                    "non_field_errors": [
                        "Las fechas planificadas de "
                        "la tarea deben encontrarse "
                        "dentro del período del "
                        "proyecto."
                    ]
                })

        # -------------------------------------
        # CANDIDATO PARA VALIDACIÓN
        # -------------------------------------

        if current:
            candidate = copy(current)
        else:
            candidate = Task()

        for field, value in attrs.items():
            setattr(candidate, field, value)

        # Ejecutar las restricciones del modelo.
        self.validate_model(candidate)

        return attrs

    # =========================================
    # CREAR TAREA
    # =========================================

    def create(self, validated_data):
        """
        Permite crear una tarea con sus
        fechas planificadas iniciales.

        La validación del proyecto y las
        fechas se mantiene activa.
        """

        instance = Task(
            **validated_data
        )

        self.validate_model(instance)

        instance.save()

        return instance

    # =========================================
    # ACTUALIZAR TAREA
    # =========================================

    def update(self, instance, validated_data):
        """
        Actualiza información general y
        datos reales de una tarea.

        Repite la protección para evitar
        que una llamada directa a save()
        del serializer omita la validación
        realizada en validate().
        """

        self.validate_planning_changes(
            instance,
            validated_data,
        )

        candidate = copy(instance)

        for field, value in validated_data.items():
            setattr(candidate, field, value)

        self.validate_model(candidate)

        # Solo después de validar modificamos
        # la instancia original.
        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()

        return instance
