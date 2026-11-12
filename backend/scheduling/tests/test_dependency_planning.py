
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from projects.models import Project
from tasks.models import Task

from scheduling.models import (
    CalendarException,
    TaskDependency,
    WorkCalendar,
)
from scheduling.services.dependency_planning import (
    DependencyPlanningService,
)
from scheduling.services.project_calendar import (
    ProjectCalendarService,
)


class DependencyPlanningServiceTests(TestCase):

    def setUp(self):
        self.project = Project.objects.create(
            code="DEPEND-PLAN-001",
            name="Proyecto de dependencias",
            description="Pruebas de planificación",
            manager_name="Responsable QA",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000000.00"),
        )

        # Viernes 13 a martes 17:
        # tres días laborables.
        self.task_a = self.create_task(
            "Diseño",
            date(2026, 11, 13),
            date(2026, 11, 17),
            3,
            1,
        )

        self.task_b = self.create_task(
            "Desarrollo",
            date(2026, 11, 13),
            date(2026, 11, 17),
            3,
            2,
        )

        self.calendar = ProjectCalendarService(
            self.project.id
        )

    def create_task(
        self,
        name,
        start,
        end,
        duration,
        position,
    ):
        return Task.objects.create(
            project=self.project,
            name=name,
            description="Actividad de prueba",
            status=Task.Status.PENDING,
            start_date=start,
            end_date=end,
            estimated_duration_days=duration,
            position=position,
        )

    def create_dependency(
        self,
        predecessor,
        successor,
        dependency_type="FS",
        lag_days=0,
    ):
        dependency = TaskDependency(
            predecessor=predecessor,
            successor=successor,
            dependency_type=dependency_type,
            lag_days=lag_days,
        )

        dependency.full_clean()
        dependency.save()

        return dependency

    def constraint(self, dependency_type, lag_days=0):
        return DependencyPlanningService.calculate_constraint(
            predecessor=self.task_a,
            dependency_type=dependency_type,
            lag_days=lag_days,
            successor_duration=3,
            calendar=self.calendar,
        )

    def test_fs_without_lag(self):
        result = self.constraint("FS")

        self.assertEqual(
            result,
            date(2026, 11, 18),
        )

    def test_ss_without_lag(self):
        result = self.constraint("SS")

        self.assertEqual(
            result,
            date(2026, 11, 13),
        )

    def test_ff_without_lag(self):
        result = self.constraint("FF")

        self.assertEqual(
            result,
            date(2026, 11, 13),
        )

    def test_sf_without_lag(self):
        result = self.constraint("SF")

        # B termina el viernes 13.
        # Su duración de tres días implica
        # comenzar el miércoles 11.
        self.assertEqual(
            result,
            date(2026, 11, 11),
        )

    def test_fs_positive_lag(self):
        result = self.constraint("FS", 2)

        self.assertEqual(
            result,
            date(2026, 11, 20),
        )

    def test_fs_negative_lag(self):
        result = self.constraint("FS", -1)

        self.assertEqual(
            result,
            date(2026, 11, 17),
        )

    def test_ff_positive_lag(self):
        result = self.constraint("FF", 2)

        # A termina el 17.
        # B debe terminar al menos el 19.
        # B dura tres días: inicia el 17.
        self.assertEqual(
            result,
            date(2026, 11, 17),
        )

    def test_reject_invalid_dependency_type(self):
        with self.assertRaises(ValidationError):
            self.constraint("XX")

    def test_multiple_predecessors(self):
        # A termina el martes 17.
        # C termina el jueves 19.
        # B debe respetar ambas dependencias FS.
        task_c = self.create_task(
            "Documentación",
            date(2026, 11, 16),
            date(2026, 11, 19),
            4,
            3,
        )

        self.create_dependency(
            self.task_a,
            self.task_b,
            "FS",
        )

        self.create_dependency(
            task_c,
            self.task_b,
            "FS",
        )

        result = (
            DependencyPlanningService.preview_successor(
                self.task_b.id
            )
        )

        self.assertEqual(
            result["start_date"],
            date(2026, 11, 20),
        )

        self.assertEqual(
            result["end_date"],
            date(2026, 11, 24),
        )

        self.assertEqual(
            result["dependencies_count"],
            2,
        )

    def test_calendar_exception_changes_fs(self):
        calendar = WorkCalendar.objects.create(
            project=self.project,
        )

        CalendarException.objects.create(
            calendar=calendar,
            date=date(2026, 11, 18),
            is_working=False,
            description="Cierre de proyecto",
        )

        self.create_dependency(
            self.task_a,
            self.task_b,
            "FS",
        )

        result = (
            DependencyPlanningService.preview_successor(
                self.task_b.id
            )
        )

        self.assertEqual(
            result["start_date"],
            date(2026, 11, 19),
        )

        self.assertEqual(
            result["end_date"],
            date(2026, 11, 23),
        )

    def test_preview_does_not_modify_database(self):
        self.create_dependency(
            self.task_a,
            self.task_b,
            "FS",
        )

        result = (
            DependencyPlanningService.preview_successor(
                self.task_b.id
            )
        )

        self.assertEqual(
            result["start_date"],
            date(2026, 11, 18),
        )

        self.task_b.refresh_from_db()

        # PostgreSQL conserva las fechas antiguas.
        self.assertEqual(
            self.task_b.start_date,
            date(2026, 11, 13),
        )

        self.assertEqual(
            self.task_b.end_date,
            date(2026, 11, 17),
        )

    def test_reject_schedule_outside_project(self):
        self.project.end_date = date(
            2026, 11, 20
        )
        self.project.save()

        # A termina el 19 de noviembre.
        # FS exige que B comience el 20.
        # B necesita tres días y termina el 24,
        # fuera del período del proyecto.
        self.task_a.start_date = date(
            2026, 11, 17
        )
        self.task_a.end_date = date(
            2026, 11, 19
        )
        self.task_a.save()

        self.create_dependency(
            self.task_a,
            self.task_b,
            "FS",
        )

        with self.assertRaises(ValidationError):
            DependencyPlanningService.preview_successor(
                self.task_b.id
            )
