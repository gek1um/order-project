
"""
Serializers de planificación - order-project.

Fase 3.5.4

Entrada:
- Fecha de inicio planificada.
- Duración estimada en días laborables.

Salida:
- Vista previa o reprogramación.
- Actividades afectadas.
- Fechas anteriores y nuevas.
"""

from rest_framework import serializers


class RescheduleRequestSerializer(
    serializers.Serializer
):
    start_date = serializers.DateField()

    duration_days = serializers.IntegerField(
        min_value=1,
        max_value=36500,
    )


class ScheduleChangeSerializer(
    serializers.Serializer
):
    task_id = serializers.IntegerField()

    name = serializers.CharField()

    old_start_date = serializers.DateField()

    old_end_date = serializers.DateField()

    new_start_date = serializers.DateField()

    new_end_date = serializers.DateField()

    estimated_duration_days = (
        serializers.IntegerField()
    )

    is_origin = serializers.BooleanField()


class ScheduleResultSerializer(
    serializers.Serializer
):
    project_id = serializers.IntegerField()

    origin_task_id = serializers.IntegerField()

    committed = serializers.BooleanField()

    affected_tasks = serializers.IntegerField()

    updated_tasks = serializers.IntegerField()

    changes = ScheduleChangeSerializer(
        many=True,
    )
