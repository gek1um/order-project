
from rest_framework import serializers

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    """
    Serializa proyectos y valida la coherencia
    de sus fechas, presupuesto y tareas asociadas.
    """

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Project

        fields = [
            "id",
            "code",
            "name",
            "description",
            "manager_name",
            "status",
            "status_display",
            "start_date",
            "end_date",
            "baseline_budget",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "status_display",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        """
        Verifica:
        - Fechas correctas.
        - Presupuesto no negativo.
        - Presupuesto inicial inmutable.
        - Coherencia con tareas existentes.
        """

        instance = self.instance

        start_date = attrs.get(
            "start_date",
            instance.start_date if instance else None,
        )

        end_date = attrs.get(
            "end_date",
            instance.end_date if instance else None,
        )

        budget = attrs.get(
            "baseline_budget",
            instance.baseline_budget if instance else None,
        )

        errors = {}

        if start_date and end_date:
            if end_date < start_date:
                errors["end_date"] = (
                    "La fecha de término no puede ser "
                    "anterior a la fecha de inicio."
                )

        if budget is not None and budget < 0:
            errors["baseline_budget"] = (
                "El presupuesto no puede ser negativo."
            )

        if instance and "baseline_budget" in attrs:
            if budget != instance.baseline_budget:
                errors["baseline_budget"] = (
                    "El presupuesto inicial no puede "
                    "modificarse después de crear "
                    "el proyecto."
                )

        if instance and start_date and end_date:
            if end_date >= start_date:
                tasks_outside = instance.tasks.exclude(
                    start_date__gte=start_date,
                    end_date__lte=end_date,
                )

                if tasks_outside.exists():
                    errors["start_date"] = (
                        "Las nuevas fechas del proyecto "
                        "dejarían tareas fuera de su "
                        "período de planificación."
                    )

        if errors:
            raise serializers.ValidationError(errors)

        return attrs
