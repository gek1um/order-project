from django.contrib.auth import get_user_model

from datetime import date
from decimal import Decimal

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project
from tasks.models import Task


class TaskPlanningProtectionTests(APITestCase):

    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code="PROTECT-001",
            name="Proyecto de protección",
            description="Pruebas del CRUD",
            manager_name="Responsable QA",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000000.00"),
        )

        self.task = Task.objects.create(
            project=self.project,
            name="Actividad original",
            description="Prueba de protección",
            status=Task.Status.PENDING,
            start_date=date(2026, 11, 13),
            end_date=date(2026, 11, 17),
            estimated_duration_days=3,
            position=1,
        )

        self.url = reverse(
            "task-detail",
            args=[self.task.id],
        )

    def test_reject_direct_start_date_change(self):
        response = self.client.patch(
            self.url,
            {"start_date": "2026-11-16"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.task.refresh_from_db()

        self.assertEqual(
            self.task.start_date,
            date(2026, 11, 13),
        )

    def test_reject_direct_end_date_change(self):
        response = self.client.patch(
            self.url,
            {"end_date": "2026-11-20"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.task.refresh_from_db()

        self.assertEqual(
            self.task.end_date,
            date(2026, 11, 17),
        )

    def test_reject_direct_duration_change(self):
        response = self.client.patch(
            self.url,
            {"estimated_duration_days": 5},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.task.refresh_from_db()

        self.assertEqual(
            self.task.estimated_duration_days,
            3,
        )

    def test_allow_general_information_update(self):
        response = self.client.patch(
            self.url,
            {
                "name": "Actividad actualizada",
                "description": "Nueva descripción",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.task.refresh_from_db()

        self.assertEqual(
            self.task.name,
            "Actividad actualizada",
        )

    def test_allow_unchanged_planning_fields(self):
        response = self.client.patch(
            self.url,
            {
                "name": "Actividad editada",
                "start_date": "2026-11-13",
                "end_date": "2026-11-17",
                "estimated_duration_days": 3,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

    def test_allow_progress_update(self):
        response = self.client.patch(
            self.url,
            {"progress_percent": "40.00"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.task.refresh_from_db()

        self.assertEqual(
            self.task.progress_percent,
            Decimal("40.00"),
        )
