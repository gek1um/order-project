from django.contrib.auth import get_user_model
"""Pruebas de regresión: cambios en calendarios y período del proyecto."""
from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project
from tasks.models import Task
from scheduling.models import CalendarException, WorkCalendar


class CalendarConsistencyAPITests(APITestCase):
    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code="CONS-CAL-1",
            name="Proyecto de consistencia",
            description="Pruebas",
            manager_name="QA",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000.00"),
        )
        self.task = self.make_task(
            "Tarea principal", date(2026, 11, 16),
            date(2026, 11, 18), 3, 1,
        )
        self.calendar_list = reverse("work-calendar-list")
        self.exception_list = reverse("calendar-exception-list")
        self.project_detail = reverse("project-detail", args=[self.project.pk])

    def make_task(self, name, start, end, duration, position):
        return Task.objects.create(
            project=self.project,
            name=name,
            description="Prueba de calendario",
            status=Task.Status.PENDING,
            start_date=start,
            end_date=end,
            estimated_duration_days=duration,
            position=position,
        )

    def make_calendar(self, **kwargs):
        return WorkCalendar.objects.create(project=self.project, **kwargs)

    def calendar_detail(self, calendar):
        return reverse("work-calendar-detail", args=[calendar.pk])

    def exception_detail(self, exception):
        return reverse("calendar-exception-detail", args=[exception.pk])

    def test_create_holiday_that_changes_duration_is_rejected(self):
        calendar = self.make_calendar()
        response = self.client.post(self.exception_list, {
            "calendar": calendar.pk, "date": "2026-11-17",
            "is_working": False,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(CalendarException.objects.count(), 0)

    def test_create_unrelated_exception_is_allowed(self):
        calendar = self.make_calendar()
        response = self.client.post(self.exception_list, {
            "calendar": calendar.pk, "date": "2026-11-22",
            "is_working": True,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(CalendarException.objects.count(), 1)

    def test_calendar_update_cannot_disable_boundary_day(self):
        calendar = self.make_calendar()
        response = self.client.patch(
            self.calendar_detail(calendar), {"monday": False}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        calendar.refresh_from_db()
        self.assertTrue(calendar.monday)

    def test_calendar_name_can_be_updated(self):
        calendar = self.make_calendar()
        response = self.client.patch(
            self.calendar_detail(calendar), {"name": "Jornada normal"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        calendar.refresh_from_db()
        self.assertEqual(calendar.name, "Jornada normal")

    def test_calendar_delete_rolls_back_when_extra_saturday_is_needed(self):
        calendar = self.make_calendar(saturday=True)
        self.make_task("Trabajo sábado", date(2026, 11, 21),
                       date(2026, 11, 21), 1, 2)
        response = self.client.delete(self.calendar_detail(calendar))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertTrue(WorkCalendar.objects.filter(pk=calendar.pk).exists())

    def test_exception_update_that_invalidates_task_is_rejected(self):
        calendar = self.make_calendar()
        exception = CalendarException.objects.create(
            calendar=calendar, date=date(2026, 11, 17), is_working=True
        )
        response = self.client.patch(self.exception_detail(exception), {
            "is_working": False,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        exception.refresh_from_db()
        self.assertTrue(exception.is_working)

    def test_delete_required_exception_is_rejected(self):
        calendar = self.make_calendar()
        exception = CalendarException.objects.create(
            calendar=calendar, date=date(2026, 11, 21), is_working=True
        )
        self.make_task("Trabajo especial", date(2026, 11, 21),
                       date(2026, 11, 21), 1, 2)
        response = self.client.delete(self.exception_detail(exception))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertTrue(CalendarException.objects.filter(pk=exception.pk).exists())

    def test_delete_holiday_that_changes_duration_is_rejected(self):
        calendar = self.make_calendar()
        exception = CalendarException.objects.create(
            calendar=calendar, date=date(2026, 11, 17), is_working=False
        )
        self.task.estimated_duration_days = 2
        self.task.save(update_fields=["estimated_duration_days"])
        response = self.client.delete(self.exception_detail(exception))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertTrue(CalendarException.objects.filter(pk=exception.pk).exists())

    def test_extend_project_end_is_allowed(self):
        response = self.client.patch(self.project_detail, {
            "end_date": "2027-01-31",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.project.refresh_from_db()
        self.assertEqual(self.project.end_date, date(2027, 1, 31))

    def test_shrink_project_around_task_is_rejected(self):
        response = self.client.patch(self.project_detail, {
            "end_date": "2026-11-17",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.project.refresh_from_db()
        self.assertEqual(self.project.end_date, date(2026, 12, 31))

    def test_unrelated_project_edit_is_allowed(self):
        response = self.client.patch(self.project_detail, {
            "name": "Proyecto editado",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_cannot_reassign_calendar_to_another_project(self):
        other = Project.objects.create(
            code="CONS-CAL-2", name="Otro proyecto", manager_name="QA",
            start_date=date(2026, 11, 1), end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000.00"),
        )
        calendar = self.make_calendar()
        response = self.client.patch(self.calendar_detail(calendar), {
            "project": other.pk,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        calendar.refresh_from_db()
        self.assertEqual(calendar.project_id, self.project.pk)

    def test_cannot_reassign_exception_to_another_calendar(self):
        other = Project.objects.create(
            code="CONS-CAL-3", name="Otro proyecto", manager_name="QA",
            start_date=date(2026, 11, 1), end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000.00"),
        )
        calendar = self.make_calendar()
        other_calendar = WorkCalendar.objects.create(project=other)
        exception = CalendarException.objects.create(
            calendar=calendar, date=date(2026, 11, 22), is_working=True
        )
        response = self.client.patch(self.exception_detail(exception), {
            "calendar": other_calendar.pk,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        exception.refresh_from_db()
        self.assertEqual(exception.calendar_id, calendar.pk)
