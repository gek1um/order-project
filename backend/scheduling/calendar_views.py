from core.access import ProjectScopedViewSetMixin

from django.db import transaction
from core.access import project_or_404
from django.shortcuts import get_object_or_404

from rest_framework import serializers, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.models import Project
from scheduling.models import (
    CalendarException,
    WorkCalendar,
)
from scheduling.calendar_serializers import (
    CalendarCalculationSerializer,
    CalendarExceptionSerializer,
    WorkCalendarSerializer,
)
from scheduling.services.calendar_consistency import ScheduleConsistencyService
from scheduling.services.project_calendar import (
    ProjectCalendarService,
)


def parse_positive_id(value, field_name):
    """
    Valida identificadores usados como filtros.
    """

    try:
        result = int(value)

        if result <= 0:
            raise ValueError

        return result

    except (TypeError, ValueError):
        raise serializers.ValidationError({
            field_name: [
                "Debe ser un entero positivo."
            ]
        })


class WorkCalendarViewSet(ProjectScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = WorkCalendarSerializer

    queryset = WorkCalendar.objects.select_related(
        "project"
    ).prefetch_related(
        "exceptions"
    ).all()

    @staticmethod
    def _lock_project(project_id):
        Project.objects.select_for_update().get(pk=project_id)

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        with transaction.atomic():
            self._lock_project(project.pk)
            before = ScheduleConsistencyService.capture(project.pk)
            calendar = serializer.save()
            ScheduleConsistencyService.validate_no_new_errors(
                calendar.project_id, before
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            calendar = WorkCalendar.objects.select_related("project").get(
                pk=serializer.instance.pk
            )
            self._lock_project(calendar.project_id)
            locked_serializer = self.get_serializer(
                calendar,
                data=serializer.initial_data,
                partial=serializer.partial,
            )
            locked_serializer.is_valid(raise_exception=True)
            before = ScheduleConsistencyService.capture(calendar.project_id)
            updated = locked_serializer.save()
            ScheduleConsistencyService.validate_no_new_errors(
                updated.project_id, before
            )

    def perform_destroy(self, instance):
        with transaction.atomic():
            self._lock_project(instance.project_id)
            before = ScheduleConsistencyService.capture(instance.project_id)
            instance.delete()
            ScheduleConsistencyService.validate_no_new_errors(
                instance.project_id, before
            )

    def get_queryset(self):
        queryset = super().get_queryset()

        project_id = self.request.query_params.get(
            "project"
        )

        if project_id is not None:
            project_id = parse_positive_id(
                project_id,
                "project",
            )

            queryset = queryset.filter(
                project_id=project_id
            )

        return queryset


class CalendarExceptionViewSet(ProjectScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = CalendarExceptionSerializer

    queryset = CalendarException.objects.select_related(
        "calendar",
        "calendar__project",
    ).all()

    def perform_create(self, serializer):
        calendar = serializer.validated_data["calendar"]
        with transaction.atomic():
            WorkCalendarViewSet._lock_project(calendar.project_id)
            before = ScheduleConsistencyService.capture(calendar.project_id)
            exception = serializer.save()
            ScheduleConsistencyService.validate_no_new_errors(
                exception.calendar.project_id, before
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            exception = CalendarException.objects.select_related(
                "calendar"
            ).get(pk=serializer.instance.pk)
            project_id = exception.calendar.project_id
            WorkCalendarViewSet._lock_project(project_id)
            locked_serializer = self.get_serializer(
                exception,
                data=serializer.initial_data,
                partial=serializer.partial,
            )
            locked_serializer.is_valid(raise_exception=True)
            before = ScheduleConsistencyService.capture(project_id)
            updated = locked_serializer.save()
            ScheduleConsistencyService.validate_no_new_errors(
                updated.calendar.project_id, before
            )

    def perform_destroy(self, instance):
        with transaction.atomic():
            project_id = instance.calendar.project_id
            WorkCalendarViewSet._lock_project(project_id)
            before = ScheduleConsistencyService.capture(project_id)
            instance.delete()
            ScheduleConsistencyService.validate_no_new_errors(
                project_id, before
            )

    def get_queryset(self):
        queryset = super().get_queryset()

        calendar_id = self.request.query_params.get(
            "calendar"
        )

        project_id = self.request.query_params.get(
            "project"
        )

        if calendar_id is not None:
            calendar_id = parse_positive_id(
                calendar_id,
                "calendar",
            )

            queryset = queryset.filter(
                calendar_id=calendar_id
            )

        if project_id is not None:
            project_id = parse_positive_id(
                project_id,
                "project",
            )

            queryset = queryset.filter(
                calendar__project_id=project_id
            )

        return queryset


class ProjectCalendarEffectiveView(APIView):
    """
    GET /api/scheduling/projects/{id}/calendar/

    Devuelve el calendario efectivo del proyecto,
    incluyendo la configuración predeterminada
    cuando todavía no existe WorkCalendar.
    """

    def get(self, request, project_id):
        project = project_or_404(request.user, project_id)

        service = ProjectCalendarService(
            project.id
        )

        return Response({
            "project_id": project.id,
            "project_code": project.code,
            "source": service.source,
            "calendar_id": (
                service.calendar.id
                if service.calendar
                else None
            ),
            "working_weekdays": sorted(
                service.working_weekdays
            ),
            "exceptions": [
                {
                    "date": day.isoformat(),
                    "is_working": is_working,
                }
                for day, is_working in sorted(
                    service.exceptions.items()
                )
            ],
        })


class ProjectCalendarCalculateView(APIView):
    """
    POST /api/scheduling/projects/{id}/calculate/

    Ejecuta cálculos usando el calendario
    configurado para el proyecto.
    """

    def post(self, request, project_id):
        project = project_or_404(request.user, project_id)

        serializer = CalendarCalculationSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        service = ProjectCalendarService(
            project.id
        )

        operation = data["operation"]
        start_date = data["start_date"]

        result = {
            "project_id": project.id,
            "project_code": project.code,
            "calendar_source": service.source,
            "operation": operation,
            "start_date": start_date.isoformat(),
        }

        try:
            if operation == "end":
                duration = data["duration_days"]

                end_date = service.calculate_end_date(
                    start_date,
                    duration,
                )

                result.update({
                    "duration_days": duration,
                    "end_date": end_date.isoformat(),
                })

            elif operation == "count":
                end_date = data["end_date"]

                total = service.count_working_days(
                    start_date,
                    end_date,
                )

                result.update({
                    "end_date": end_date.isoformat(),
                    "working_days": total,
                })

            elif operation == "shift":
                offset = data["offset_days"]

                result_date = service.shift_working_days(
                    start_date,
                    offset,
                )

                result.update({
                    "offset_days": offset,
                    "result_date": result_date.isoformat(),
                })

            elif operation == "is_working_day":
                result["is_working"] = (
                    service.is_working_day(start_date)
                )

        except (ValueError, OverflowError) as exc:
            raise serializers.ValidationError({
                "non_field_errors": [str(exc)]
            }) from exc

        return Response(
            result,
            status=status.HTTP_200_OK,
        )
