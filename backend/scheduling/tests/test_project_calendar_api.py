from django.contrib.auth import get_user_model

from datetime import date
from decimal import Decimal

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project
from scheduling.models import (
    CalendarException,
    WorkCalendar,
)
from scheduling.services.project_calendar import (
    ProjectCalendarService,
)


class ProjectCalendarAPITests(APITestCase):

    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code="CAL-API-001",
            name="Proyecto calendario API",
            description="Pruebas integrales",
            manager_name="Responsable QA",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000000.00"),
        )

        self.calendars_url = reverse(
            "work-calendar-list"
        )

        self.exceptions_url = reverse(
            "calendar-exception-list"
        )

        self.calculate_url = reverse(
            "project-calendar-calculate",
            args=[self.project.id],
        )

        self.effective_url = reverse(
            "project-effective-calendar",
            args=[self.project.id],
        )

    def create_calendar(self, **kwargs):
        return WorkCalendar.objects.create(
            project=self.project,
            **kwargs,
        )

    def test_default_calendar_without_configuration(self):
        service = ProjectCalendarService(
            self.project.id
        )

        self.assertEqual(
            service.source,
            "default",
        )

        self.assertEqual(
            service.working_weekdays,
            frozenset({0, 1, 2, 3, 4}),
        )

    def test_get_effective_default_calendar(self):
        response = self.client.get(
            self.effective_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["source"],
            "default",
        )

        self.assertEqual(
            response.data["working_weekdays"],
            [0, 1, 2, 3, 4],
        )

    def test_create_calendar_from_api(self):
        response = self.client.post(
            self.calendars_url,
            {
                "project": self.project.id,
                "name": "Calendario de seis días",
                "saturday": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        self.assertIn(
            5,
            response.data["working_weekdays"],
        )

    def test_reject_duplicate_project_calendar(self):
        self.create_calendar()

        response = self.client.post(
            self.calendars_url,
            {
                "project": self.project.id,
                "name": "Calendario duplicado",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_calculate_end_with_default_calendar(self):
        response = self.client.post(
            self.calculate_url,
            {
                "operation": "end",
                "start_date": "2026-11-13",
                "duration_days": 3,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(
            response.data["end_date"],
            "2026-11-17",
        )

    def test_non_working_exception_changes_end_date(self):
        calendar = self.create_calendar()

        CalendarException.objects.create(
            calendar=calendar,
            date=date(2026, 11, 16),
            is_working=False,
        )

        response = self.client.post(
            self.calculate_url,
            {
                "operation": "end",
                "start_date": "2026-11-13",
                "duration_days": 3,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(
            response.data["end_date"],
            "2026-11-18",
        )

    def test_extra_working_saturday_is_counted(self):
        calendar = self.create_calendar()

        CalendarException.objects.create(
            calendar=calendar,
            date=date(2026, 11, 14),
            is_working=True,
        )

        response = self.client.post(
            self.calculate_url,
            {
                "operation": "end",
                "start_date": "2026-11-13",
                "duration_days": 3,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(
            response.data["end_date"],
            "2026-11-16",
        )

    def test_count_days_with_exception(self):
        calendar = self.create_calendar()

        CalendarException.objects.create(
            calendar=calendar,
            date=date(2026, 11, 16),
            is_working=False,
        )

        response = self.client.post(
            self.calculate_url,
            {
                "operation": "count",
                "start_date": "2026-11-13",
                "end_date": "2026-11-17",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(
            response.data["working_days"],
            2,
        )

    def test_negative_shift(self):
        response = self.client.post(
            self.calculate_url,
            {
                "operation": "shift",
                "start_date": "2026-11-16",
                "offset_days": -1,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(
            response.data["result_date"],
            "2026-11-13",
        )

    def test_reject_invalid_duration(self):
        response = self.client.post(
            self.calculate_url,
            {
                "operation": "end",
                "start_date": "2026-11-13",
                "duration_days": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
