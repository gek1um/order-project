"""Pruebas independientes del auditor del cronograma."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from projects.models import Project
from tasks.models import Task
from scheduling.models import TaskDependency, WorkCalendar, CalendarException
from scheduling.services.schedule_audit import ScheduleAuditService


class ScheduleAuditTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(
            code="AUD-001", name="Proyecto auditoría", manager_name="QA",
            start_date=date(2026, 11, 1), end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000.00"),
        )
        self.a = self.task("A", date(2026, 11, 13), date(2026, 11, 17), 3, 1)
        self.b = self.task("B", date(2026, 11, 18), date(2026, 11, 20), 3, 2)

    def task(self, name, start, end, duration, position):
        return Task.objects.create(
            project=self.project, name=name,
            start_date=start, end_date=end,
            estimated_duration_days=duration, position=position,
        )

    def codes(self):
        return [issue["code"] for issue in ScheduleAuditService.audit(self.project.id)["issues"]]

    def test_valid_schedule(self):
        self.assertTrue(ScheduleAuditService.audit(self.project.id)["valid"])

    def test_detects_dates_outside_project(self):
        self.b.end_date = date(2027, 1, 4)
        self.b.save()
        self.assertIn("OUTSIDE_PROJECT", self.codes())

    def test_detects_non_working_boundary(self):
        self.b.start_date = date(2026, 11, 21)
        self.b.end_date = date(2026, 11, 24)
        self.b.save()
        self.assertIn("NON_WORKING_BOUNDARY", self.codes())

    def test_detects_duration_mismatch(self):
        self.b.estimated_duration_days = 2
        self.b.save()
        self.assertIn("DURATION_MISMATCH", self.codes())

    def test_missing_duration_only_warning(self):
        self.b.estimated_duration_days = None
        self.b.save()
        result = ScheduleAuditService.audit(self.project.id)
        self.assertTrue(result["valid"])
        self.assertIn("MISSING_DURATION", self.codes())

    def test_detects_dependency_violation(self):
        TaskDependency.objects.create(predecessor=self.a, successor=self.b, dependency_type="FS")
        self.b.start_date = date(2026, 11, 17)
        self.b.end_date = date(2026, 11, 19)
        self.b.save()
        self.assertIn("DEPENDENCY_VIOLATION", self.codes())

    def test_valid_dependency(self):
        TaskDependency.objects.create(predecessor=self.a, successor=self.b, dependency_type="FS")
        self.assertTrue(ScheduleAuditService.audit(self.project.id)["valid"])

    def test_calendar_exception_affects_dates(self):
        calendar = WorkCalendar.objects.create(project=self.project)
        CalendarException.objects.create(
            calendar=calendar, date=date(2026, 11, 18), is_working=False
        )
        self.assertIn("NON_WORKING_BOUNDARY", self.codes())

    def test_audit_never_writes_to_database(self):
        original = self.b.start_date
        ScheduleAuditService.audit(self.project.id)
        self.b.refresh_from_db()
        self.assertEqual(self.b.start_date, original)
