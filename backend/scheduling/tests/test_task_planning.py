
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from projects.models import Project
from tasks.models import Task

from scheduling.models import (
    CalendarException,
    WorkCalendar,
)

from scheduling.services.task_planning import (
    TaskPlanningService,
)


class TaskPlanningServiceTests(TestCase):
    """
    Pruebas de planificación individual.

    Verifica:
    - Cálculo de fechas.
    - Duraciones laborales.
    - Excepciones de calendario.
    - Reprogramación persistente.
    - Integridad ante errores.
    """

    def setUp(self):
        self.project = Project.objects.create(
            code="PLAN-001",
            name="Proyecto de planificación",
            description="Pruebas fase 3.5.1",
            manager_name="Responsable QA",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000000.00"),
        )

        self.task = Task.objects.create(
            project=self.project,
            name="Actividad de prueba",
            description="Prueba de calendario",
            status=Task.Status.PENDING,
            start_date=date(2026, 11, 13),
            end_date=date(2026, 11, 17),
            position=1,
        )

        self.friday = date(2026, 11, 13)

    def test_calculate_end_default_calendar(self):
        result = TaskPlanningService.calculate_end(
            self.project,
            self.friday,
            3,
        )

        self.assertEqual(
            result,
            date(2026, 11, 17),
        )

    def test_calculate_duration_default_calendar(self):
        result = TaskPlanningService.calculate_duration(
            self.project,
            self.friday,
            date(2026, 11, 17),
        )

        self.assertEqual(result, 3)

    def test_calculate_end_with_holiday(self):
        calendar = WorkCalendar.objects.create(
            project=self.project,
        )

        CalendarException.objects.create(
            calendar=calendar,
            date=date(2026, 11, 16),
            is_working=False,
            description="Cierre excepcional",
        )

        result = TaskPlanningService.calculate_end(
            self.project,
            self.friday,
            3,
        )

        self.assertEqual(
            result,
            date(2026, 11, 18),
        )

    def test_calculate_end_with_extra_saturday(self):
        calendar = WorkCalendar.objects.create(
            project=self.project,
        )

        CalendarException.objects.create(
            calendar=calendar,
            date=date(2026, 11, 14),
            is_working=True,
            description="Jornada extraordinaria",
        )

        result = TaskPlanningService.calculate_end(
            self.project,
            self.friday,
            3,
        )

        self.assertEqual(
            result,
            date(2026, 11, 16),
        )

    def test_reject_non_working_start(self):
        with self.assertRaises(ValidationError):
            TaskPlanningService.calculate_end(
                self.project,
                date(2026, 11, 14),
                3,
            )

    def test_reject_zero_duration(self):
        with self.assertRaises(ValidationError):
            TaskPlanningService.calculate_end(
                self.project,
                self.friday,
                0,
            )

    def test_reject_schedule_outside_project(self):
        with self.assertRaises(ValidationError):
            TaskPlanningService.calculate_end(
                self.project,
                date(2026, 12, 30),
                5,
            )

    def test_preview_does_not_modify_database(self):
        result = TaskPlanningService.preview(
            self.project,
            self.friday,
            5,
        )

        self.assertEqual(
            result["end_date"],
            date(2026, 11, 19),
        )

        self.task.refresh_from_db()

        self.assertEqual(
            self.task.end_date,
            date(2026, 11, 17),
        )

        self.assertIsNone(
            self.task.estimated_duration_days
        )

    def test_reschedule_updates_database(self):
        updated = TaskPlanningService.reschedule(
            self.task.id,
            self.friday,
            5,
        )

        self.assertEqual(
            updated.end_date,
            date(2026, 11, 19),
        )

        self.task.refresh_from_db()

        self.assertEqual(
            self.task.start_date,
            self.friday,
        )

        self.assertEqual(
            self.task.end_date,
            date(2026, 11, 19),
        )

        self.assertEqual(
            self.task.estimated_duration_days,
            5,
        )

    def test_failed_reschedule_keeps_old_dates(self):
        old_start = self.task.start_date
        old_end = self.task.end_date

        with self.assertRaises(ValidationError):
            TaskPlanningService.reschedule(
                self.task.id,
                date(2026, 12, 30),
                10,
            )

        self.task.refresh_from_db()

        self.assertEqual(
            self.task.start_date,
            old_start,
        )

        self.assertEqual(
            self.task.end_date,
            old_end,
        )

        self.assertIsNone(
            self.task.estimated_duration_days
        )

    def test_reschedule_preserves_actual_dates(self):
        self.task.actual_start_date = date(
            2026, 11, 13
        )

        self.task.progress_percent = Decimal(
            "25.00"
        )

        self.task.save()

        TaskPlanningService.reschedule(
            self.task.id,
            self.friday,
            5,
        )

        self.task.refresh_from_db()

        self.assertEqual(
            self.task.actual_start_date,
            date(2026, 11, 13),
        )

        self.assertEqual(
            self.task.progress_percent,
            Decimal("25.00"),
        )

    def test_reject_non_working_end(self):
        with self.assertRaises(ValidationError):
            TaskPlanningService.calculate_duration(
                self.project,
                self.friday,
                date(2026, 11, 15),
            )
