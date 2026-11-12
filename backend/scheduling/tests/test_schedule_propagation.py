
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

from scheduling.services.schedule_propagation import (
    SchedulePropagationService,
)


class SchedulePropagationTests(TestCase):

    def setUp(self):
        self.project = Project.objects.create(
            code="PROP-001",
            name="Proyecto de propagación",
            description="Pruebas fase 3.5.3",
            manager_name="Responsable QA",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000000.00"),
        )

        self.a = self.create_task(
            "Diseño",
            "2026-11-13",
            "2026-11-17",
            3,
            1,
        )

        self.b = self.create_task(
            "Desarrollo",
            "2026-11-18",
            "2026-11-20",
            3,
            2,
        )

        self.c = self.create_task(
            "Pruebas",
            "2026-11-23",
            "2026-11-24",
            2,
            3,
        )

        self.d = self.create_task(
            "Tarea independiente",
            "2026-11-16",
            "2026-11-16",
            1,
            4,
        )

        self.ab = self.create_dependency(
            self.a,
            self.b,
            "FS",
        )

        self.bc = self.create_dependency(
            self.b,
            self.c,
            "FS",
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
            start_date=date.fromisoformat(start),
            end_date=date.fromisoformat(end),
            estimated_duration_days=duration,
            position=position,
        )

    def create_dependency(
        self,
        predecessor,
        successor,
        dependency_type,
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

    def propagate(self, duration=5, commit=True):
        return SchedulePropagationService.propagate(
            task_id=self.a.id,
            start_date=date(2026, 11, 13),
            duration_days=duration,
            commit=commit,
        )

    def refresh_tasks(self):
        for task in [self.a, self.b, self.c, self.d]:
            task.refresh_from_db()

    def test_propagates_fs_chain(self):
        result = self.propagate()

        self.refresh_tasks()

        self.assertEqual(
            self.a.end_date,
            date(2026, 11, 19),
        )

        self.assertEqual(
            self.b.start_date,
            date(2026, 11, 20),
        )

        self.assertEqual(
            self.b.end_date,
            date(2026, 11, 24),
        )

        self.assertEqual(
            self.c.start_date,
            date(2026, 11, 25),
        )

        self.assertEqual(
            self.c.end_date,
            date(2026, 11, 26),
        )

        self.assertEqual(
            result["updated_tasks"],
            3,
        )

    def test_preview_does_not_save(self):
        result = self.propagate(
            duration=5,
            commit=False,
        )

        self.assertFalse(result["committed"])

        self.assertEqual(
            result["updated_tasks"],
            3,
        )

        self.refresh_tasks()

        self.assertEqual(
            self.a.end_date,
            date(2026, 11, 17),
        )

        self.assertEqual(
            self.b.start_date,
            date(2026, 11, 18),
        )

        self.assertEqual(
            self.c.start_date,
            date(2026, 11, 23),
        )

    def test_unrelated_task_is_unchanged(self):
        self.propagate()

        self.d.refresh_from_db()

        self.assertEqual(
            self.d.start_date,
            date(2026, 11, 16),
        )

        self.assertEqual(
            self.d.end_date,
            date(2026, 11, 16),
        )

    def test_same_schedule_has_no_changes(self):
        result = self.propagate(duration=3)

        self.assertEqual(
            result["updated_tasks"],
            0,
        )

    def test_keeps_successor_planned_later(self):
        self.b.start_date = date(2026, 11, 25)
        self.b.end_date = date(2026, 11, 27)
        self.b.save()

        self.c.start_date = date(2026, 11, 30)
        self.c.end_date = date(2026, 12, 1)
        self.c.save()

        result = self.propagate(duration=5)

        self.refresh_tasks()

        self.assertEqual(
            self.b.start_date,
            date(2026, 11, 25),
        )

        self.assertEqual(
            self.c.start_date,
            date(2026, 11, 30),
        )

        self.assertEqual(
            result["updated_tasks"],
            1,
        )

    def test_multiple_predecessors(self):
        self.create_dependency(
            self.d,
            self.b,
            "FS",
            lag_days=8,
        )

        self.propagate(duration=5)

        self.refresh_tasks()

        # D termina el 16.
        # FS comienza a contar desde el 17.
        # Con lag +8, B comienza el 27.
        self.assertEqual(
            self.b.start_date,
            date(2026, 11, 27),
        )

        self.assertEqual(
            self.b.end_date,
            date(2026, 12, 1),
        )

        self.assertEqual(
            self.c.start_date,
            date(2026, 12, 2),
        )

    def test_respects_calendar_exception(self):
        calendar = WorkCalendar.objects.create(
            project=self.project,
        )

        CalendarException.objects.create(
            calendar=calendar,
            date=date(2026, 11, 20),
            is_working=False,
            description="Cierre extraordinario",
        )

        self.propagate(duration=5)

        self.refresh_tasks()

        self.assertEqual(
            self.b.start_date,
            date(2026, 11, 23),
        )

        self.assertEqual(
            self.b.end_date,
            date(2026, 11, 25),
        )

        self.assertEqual(
            self.c.start_date,
            date(2026, 11, 26),
        )

    def test_finish_to_finish_dependency(self):
        self.ab.dependency_type = "FF"
        self.ab.lag_days = 2
        self.ab.full_clean()
        self.ab.save()

        self.propagate(duration=5)

        self.refresh_tasks()

        self.assertEqual(
            self.b.start_date,
            date(2026, 11, 19),
        )

        self.assertEqual(
            self.b.end_date,
            date(2026, 11, 23),
        )

        self.assertEqual(
            self.c.start_date,
            date(2026, 11, 24),
        )

    def test_start_to_start_dependency(self):
        self.ab.dependency_type = "SS"
        self.ab.lag_days = 5
        self.ab.full_clean()
        self.ab.save()

        self.propagate(duration=5)

        self.b.refresh_from_db()

        self.assertEqual(
            self.b.start_date,
            date(2026, 11, 20),
        )

    def test_negative_lag(self):
        self.ab.lag_days = -1
        self.ab.full_clean()
        self.ab.save()

        self.propagate(duration=5)

        self.b.refresh_from_db()

        self.assertEqual(
            self.b.start_date,
            date(2026, 11, 19),
        )

    def test_rollback_if_project_end_exceeded(self):
        self.project.end_date = date(
            2026, 11, 25
        )
        self.project.save()

        with self.assertRaises(ValidationError):
            self.propagate(duration=5)

        self.refresh_tasks()

        self.assertEqual(
            self.a.end_date,
            date(2026, 11, 17),
        )

        self.assertEqual(
            self.b.start_date,
            date(2026, 11, 18),
        )

        self.assertEqual(
            self.c.start_date,
            date(2026, 11, 23),
        )

    def test_reject_moving_started_successor(self):
        self.b.status = Task.Status.IN_PROGRESS
        self.b.actual_start_date = date(
            2026, 11, 18
        )
        self.b.save()

        with self.assertRaises(ValidationError):
            self.propagate(duration=5)

        self.refresh_tasks()

        self.assertEqual(
            self.a.end_date,
            date(2026, 11, 17),
        )

        self.assertEqual(
            self.b.start_date,
            date(2026, 11, 18),
        )

    def test_reject_reprogramming_started_origin(self):
        self.a.status = Task.Status.IN_PROGRESS
        self.a.actual_start_date = date(
            2026, 11, 13
        )
        self.a.save()

        with self.assertRaises(ValidationError):
            self.propagate(duration=5)

        self.a.refresh_from_db()

        self.assertEqual(
            self.a.end_date,
            date(2026, 11, 17),
        )
