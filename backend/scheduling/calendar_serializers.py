from core.access import ScopedRelationsMixin

from copy import copy

from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)

from rest_framework import serializers

from projects.models import Project
from scheduling.models import (
    CalendarException,
    WorkCalendar,
)


def validate_candidate(candidate):
    """
    Ejecuta las validaciones de Django
    y las convierte en errores de DRF.
    """

    try:
        candidate.full_clean()

    except DjangoValidationError as exc:
        if hasattr(exc, "message_dict"):
            raise serializers.ValidationError(
                exc.message_dict
            ) from exc

        raise serializers.ValidationError({
            "non_field_errors": exc.messages
        }) from exc


class CalendarExceptionSerializer(
    ScopedRelationsMixin, serializers.ModelSerializer
):
    calendar = serializers.PrimaryKeyRelatedField(
        queryset=WorkCalendar.objects.all()
    )

    class Meta:
        model = CalendarException

        fields = [
            "id",
            "calendar",
            "date",
            "is_working",
            "description",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        current = self.instance

        if current is not None and "calendar" in attrs:
            if attrs["calendar"].pk != current.calendar_id:
                raise serializers.ValidationError({
                    "calendar": [
                        "No se permite trasladar una excepción a otro calendario."
                    ]
                })

        candidate = (
            copy(current)
            if current
            else CalendarException()
        )

        for field, value in attrs.items():
            setattr(candidate, field, value)

        validate_candidate(candidate)
        return attrs

    def create(self, validated_data):
        instance = CalendarException(
            **validated_data
        )
        validate_candidate(instance)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)

        validate_candidate(instance)
        instance.save()
        return instance


class WorkCalendarSerializer(
    ScopedRelationsMixin, serializers.ModelSerializer
):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all()
    )

    working_weekdays = serializers.SerializerMethodField()

    exceptions = CalendarExceptionSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = WorkCalendar

        fields = [
            "id",
            "project",
            "name",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "working_weekdays",
            "exceptions",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "working_weekdays",
            "exceptions",
            "created_at",
            "updated_at",
        ]

    def get_working_weekdays(self, obj):
        return sorted(obj.working_weekdays)

    def validate(self, attrs):
        current = self.instance

        if current is not None and "project" in attrs:
            if attrs["project"].pk != current.project_id:
                raise serializers.ValidationError({
                    "project": [
                        "No se permite trasladar un calendario a otro proyecto."
                    ]
                })

        candidate = (
            copy(current)
            if current
            else WorkCalendar()
        )

        for field, value in attrs.items():
            setattr(candidate, field, value)

        validate_candidate(candidate)
        return attrs

    def create(self, validated_data):
        instance = WorkCalendar(**validated_data)

        validate_candidate(instance)
        instance.save()

        return instance

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)

        validate_candidate(instance)
        instance.save()

        return instance


class CalendarCalculationSerializer(
    serializers.Serializer
):
    """
    Entrada para operaciones de fechas.

    Operaciones:
    - end: obtener término desde duración.
    - count: contar días laborables.
    - shift: desplazar una fecha.
    - is_working_day: consultar una fecha.
    """

    operation = serializers.ChoiceField(
        choices=[
            "end",
            "count",
            "shift",
            "is_working_day",
        ]
    )

    start_date = serializers.DateField()

    end_date = serializers.DateField(
        required=False,
    )

    duration_days = serializers.IntegerField(
        required=False,
        min_value=1,
    )

    offset_days = serializers.IntegerField(
        required=False,
    )

    def validate(self, attrs):
        operation = attrs["operation"]

        if operation == "end":
            if "duration_days" not in attrs:
                raise serializers.ValidationError({
                    "duration_days": [
                        "Este campo es obligatorio "
                        "para calcular el término."
                    ]
                })

        elif operation == "count":
            if "end_date" not in attrs:
                raise serializers.ValidationError({
                    "end_date": [
                        "Este campo es obligatorio "
                        "para contar días."
                    ]
                })

            if attrs["end_date"] < attrs["start_date"]:
                raise serializers.ValidationError({
                    "end_date": [
                        "El término no puede ser "
                        "anterior al inicio."
                    ]
                })

        elif operation == "shift":
            if "offset_days" not in attrs:
                raise serializers.ValidationError({
                    "offset_days": [
                        "Este campo es obligatorio "
                        "para desplazar fechas."
                    ]
                })

        return attrs
