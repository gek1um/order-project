from core.access import ScopedRelationsMixin

from copy import copy

from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)

from rest_framework import serializers

from tasks.models import Task

from .models import TaskDependency


class TaskDependencySerializer(ScopedRelationsMixin, serializers.ModelSerializer):
    """
    Serializador REST de dependencias temporales.

    Funcionalidades:
    - Crear dependencias entre tareas.
    - Actualizar dependencias existentes.
    - Soportar FS, SS, FF y SF.
    - Soportar desfases positivos y negativos.
    - Rechazar autodependencias.
    - Rechazar dependencias duplicadas.
    - Rechazar ciclos.
    - Impedir relaciones entre proyectos diferentes.
    """

    predecessor = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all()
    )

    successor = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all()
    )

    predecessor_name = serializers.CharField(
        source="predecessor.name",
        read_only=True,
    )

    successor_name = serializers.CharField(
        source="successor.name",
        read_only=True,
    )

    project_id = serializers.IntegerField(
        source="predecessor.project_id",
        read_only=True,
    )

    project_code = serializers.CharField(
        source="predecessor.project.code",
        read_only=True,
    )

    dependency_type_display = serializers.CharField(
        source="get_dependency_type_display",
        read_only=True,
    )

    class Meta:
        model = TaskDependency

        fields = [
            "id",
            "project_id",
            "project_code",
            "predecessor",
            "predecessor_name",
            "successor",
            "successor_name",
            "dependency_type",
            "dependency_type_display",
            "lag_days",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "project_id",
            "project_code",
            "predecessor_name",
            "successor_name",
            "dependency_type_display",
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
        respuestas HTTP 400 compatibles con DRF.
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
    # VALIDACIÓN DE DATOS
    # =========================================

    def validate(self, attrs):
        """
        Valida el estado final de la dependencia.

        En las actualizaciones PATCH conserva
        los campos que no fueron enviados.

        Utiliza copy() para conservar el estado
        interno de la instancia de Django.
        """

        current = self.instance

        # -------------------------------------
        # PREDECESORA Y SUCESORA
        # -------------------------------------

        predecessor = attrs.get(
            "predecessor",
            current.predecessor if current else None,
        )

        successor = attrs.get(
            "successor",
            current.successor if current else None,
        )

        # -------------------------------------
        # VALIDAR PROYECTO ORIGINAL
        # -------------------------------------

        if current and predecessor and successor:
            current_project_id = (
                current.predecessor.project_id
            )

            if (
                predecessor.project_id != current_project_id
                or successor.project_id != current_project_id
            ):
                raise serializers.ValidationError({
                    "non_field_errors": [
                        "No se permite trasladar una dependencia "
                        "a otro proyecto. Elimínala y crea una "
                        "nueva en el proyecto correspondiente."
                    ]
                })

        # -------------------------------------
        # CANDIDATO PARA VALIDACIÓN
        # -------------------------------------

        if current:
            # Conservamos el estado interno del
            # registro existente en PostgreSQL.
            candidate = copy(current)
        else:
            # Estamos creando una dependencia nueva.
            candidate = TaskDependency()

        # Aplicamos al candidato los nuevos valores.
        for field, value in attrs.items():
            setattr(candidate, field, value)

        # Ejecutamos las validaciones del modelo:
        # ciclos, proyectos, duplicados y tipos.
        self.validate_model(candidate)

        return attrs

    # =========================================
    # CREAR DEPENDENCIA
    # =========================================

    def create(self, validated_data):
        """
        Crea una dependencia nueva.

        Se valida nuevamente inmediatamente
        antes de guardar.
        """

        instance = TaskDependency(**validated_data)

        self.validate_model(instance)

        instance.save()

        return instance

    # =========================================
    # ACTUALIZAR DEPENDENCIA
    # =========================================

    def update(self, instance, validated_data):
        """
        Actualiza una dependencia existente.

        Conserva el estado del registro original,
        evitando errores falsos de duplicidad.
        """

        for field, value in validated_data.items():
            setattr(instance, field, value)

        self.validate_model(instance)

        instance.save()

        return instance
