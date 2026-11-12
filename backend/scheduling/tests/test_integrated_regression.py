from django.contrib.auth import get_user_model
"""Regresión integral de planificación: Fase 3.6.6.4.

Prueba flujos que cruzan CRUD, dependencias, calendarios, reprogramación
transaccional y auditoría. Solo utiliza una base de datos de pruebas.
"""
from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project
from tasks.models import Task
from scheduling.models import TaskDependency, WorkCalendar, CalendarException
from scheduling.services.schedule_audit import ScheduleAuditService


class IntegratedScheduleRegressionTests(APITestCase):
    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code="E2E-3664", name="Proyecto regresión integral",
            description="Planificación", manager_name="QA",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1), end_date=date(2026, 12, 31),
            baseline_budget=Decimal("10000.00"),
        )
        self.a = self.make_task("Diseño", 1, 13, 17, 3)
        self.b = self.make_task("Desarrollo", 2, 18, 20, 3)
        self.c = self.make_task("Pruebas", 3, 23, 24, 2)
        self.dependency_list = reverse("task-dependency-list")
        self.calendar_list = reverse("work-calendar-list")
        self.exception_list = reverse("calendar-exception-list")
        self.project_url = reverse("project-detail", args=[self.project.pk])
        self.preview_url = reverse("task-schedule-preview", args=[self.a.pk])
        self.reschedule_url = reverse("task-schedule-reschedule", args=[self.a.pk])
        self.schedule_url = reverse("project-schedule", args=[self.project.pk])

    def make_task(self, name, position, start_day, end_day, duration):
        return Task.objects.create(
            project=self.project, name=name, position=position,
            status=Task.Status.PENDING,
            start_date=date(2026, 11, start_day),
            end_date=date(2026, 11, end_day),
            estimated_duration_days=duration,
        )

    def link(self, source, target, kind="FS", lag=0):
        return self.client.post(self.dependency_list, {
            "predecessor": source.pk, "successor": target.pk,
            "dependency_type": kind, "lag_days": lag,
        }, format="json")

    def schedule_change(self, url, duration=5):
        return self.client.post(url, {
            "start_date": "2026-11-13", "duration_days": duration,
        }, format="json")

    def assert_valid_audit(self):
        report = ScheduleAuditService.audit(self.project.pk)
        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["errors_count"], 0)

    def test_valid_dependencies_preview_then_commit_end_to_end(self):
        for source, target in ((self.a, self.b), (self.b, self.c)):
            response = self.link(source, target)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assert_valid_audit()

        preview = self.schedule_change(self.preview_url)
        self.assertEqual(preview.status_code, status.HTTP_200_OK, preview.data)
        self.assertFalse(preview.data["committed"])
        self.assertEqual(preview.data["updated_tasks"], 3)
        self.a.refresh_from_db()
        self.assertEqual(self.a.end_date, date(2026, 11, 17))

        applied = self.schedule_change(self.reschedule_url)
        self.assertEqual(applied.status_code, status.HTTP_200_OK, applied.data)
        self.assertTrue(applied.data["committed"])
        self.a.refresh_from_db()
        self.b.refresh_from_db()
        self.c.refresh_from_db()
        self.assertEqual(self.a.end_date, date(2026, 11, 19))
        self.assertEqual(self.b.start_date, date(2026, 11, 20))
        self.assertEqual(self.c.start_date, date(2026, 11, 25))
        self.assert_valid_audit()

        schedule = self.client.get(self.schedule_url)
        self.assertEqual(schedule.status_code, status.HTTP_200_OK)
        self.assertEqual(schedule.data["tasks_count"], 3)
        self.assertEqual(schedule.data["dependencies_count"], 2)

    def test_invalid_dependency_does_not_persist(self):
        response = self.link(self.b, self.a)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(TaskDependency.objects.count(), 0)
        self.assert_valid_audit()

    def test_invalid_dependency_patch_rolls_back(self):
        created = self.link(self.a, self.b)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        dependency = TaskDependency.objects.get(pk=created.data["id"])
        patched = self.client.patch(
            reverse("task-dependency-detail", args=[dependency.pk]),
            {"lag_days": 4}, format="json",
        )
        self.assertEqual(patched.status_code, status.HTTP_400_BAD_REQUEST)
        dependency.refresh_from_db()
        self.assertEqual(dependency.lag_days, 0)
        self.assert_valid_audit()

    def test_calendar_holiday_conflict_rolls_back(self):
        created = self.client.post(self.calendar_list, {
            "project": self.project.pk, "name": "Semana laboral",
        }, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        response = self.client.post(self.exception_list, {
            "calendar": created.data["id"],
            "date": "2026-11-19", "is_working": False,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(CalendarException.objects.filter(date=date(2026, 11, 19)).exists())
        self.assert_valid_audit()

    def test_unrelated_calendar_exception_is_allowed(self):
        calendar = WorkCalendar.objects.create(project=self.project)
        response = self.client.post(self.exception_list, {
            "calendar": calendar.pk,
            "date": "2026-11-28", "is_working": True,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(CalendarException.objects.filter(calendar=calendar, date=date(2026, 11, 28)).exists())
        self.assert_valid_audit()

    def test_project_shrink_is_rejected_without_changing_dates(self):
        response = self.client.patch(self.project_url, {
            "end_date": "2026-11-19",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.project.refresh_from_db()
        self.assertEqual(self.project.end_date, date(2026, 12, 31))
        self.assert_valid_audit()

    def test_direct_task_date_edit_is_rejected(self):
        response = self.client.patch(
            reverse("task-detail", args=[self.b.pk]),
            {"start_date": "2026-11-19"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.b.refresh_from_db()
        self.assertEqual(self.b.start_date, date(2026, 11, 18))
        self.assert_valid_audit()

    def test_started_successor_causes_full_reschedule_rollback(self):
        created = self.link(self.a, self.b)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.b.status = Task.Status.IN_PROGRESS
        self.b.actual_start_date = date(2026, 11, 18)
        self.b.save(update_fields=["status", "actual_start_date"])

        response = self.schedule_change(self.reschedule_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.a.refresh_from_db()
        self.b.refresh_from_db()
        self.assertEqual(self.a.end_date, date(2026, 11, 17))
        self.assertEqual(self.b.start_date, date(2026, 11, 18))
        self.assert_valid_audit()
