from django.contrib.auth import get_user_model

from datetime import date
from decimal import Decimal

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project
from tasks.models import Task


class TaskTemporalAPITests(APITestCase):
    """
    Pruebas de la ampliación temporal de Task.

    Comprueba:
    - Compatibilidad con el CRUD anterior.
    - Campos nuevos disponibles en la API.
    - Fechas reales.
    - Avance porcentual.
    - Duraciones.
    - Rechazo de datos inválidos.
    """

    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code="TEMP-API-001",
            name="Proyecto temporal",
            description="Pruebas de programación",
            manager_name="Responsable QA",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000000.00"),
        )

        self.task = Task.objects.create(
            project=self.project,
            name="Actividad temporal",
            description="Prueba de integración",
            status=Task.Status.PENDING,
            start_date=date(2026, 11, 10),
            end_date=date(2026, 11, 20),
            position=1,
        )

        self.detail_url = reverse(
            "task-detail",
            args=[self.task.id],
        )

        self.list_url = reverse("task-list")

    def test_get_includes_temporal_fields(self):
        response = self.client.get(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn(
            "actual_start_date",
            response.data,
        )

        self.assertIn(
            "actual_end_date",
            response.data,
        )

        self.assertIn(
            "estimated_duration_days",
            response.data,
        )

        self.assertIn(
            "actual_duration_days",
            response.data,
        )

        self.assertIn(
            "progress_percent",
            response.data,
        )

    def test_update_progress_successfully(self):
        response = self.client.patch(
            self.detail_url,
            {
                "progress_percent": "35.50",
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
            self.task.progress_percent,
            Decimal("35.50"),
        )

    def test_reject_progress_above_100(self):
        response = self.client.patch(
            self.detail_url,
            {
                "progress_percent": "120.00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.task.refresh_from_db()

        self.assertEqual(
            self.task.progress_percent,
            Decimal("0.00"),
        )

    def test_reject_negative_progress(self):
        response = self.client.patch(
            self.detail_url,
            {
                "progress_percent": "-10.00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_register_actual_start_date(self):
        response = self.client.patch(
            self.detail_url,
            {
                "actual_start_date": "2026-11-12",
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
            self.task.actual_start_date,
            date(2026, 11, 12),
        )

    def test_reject_actual_end_before_start(self):
        response = self.client.patch(
            self.detail_url,
            {
                "actual_start_date": "2026-11-15",
                "actual_end_date": "2026-11-10",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_reject_actual_end_without_start(self):
        response = self.client.patch(
            self.detail_url,
            {
                "actual_end_date": "2026-11-20",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_reject_direct_estimated_duration_update(self):
        """
        Comprueba que el CRUD convencional
        no permita modificar directamente
        la duración estimada.

        Las modificaciones de planificación
        deben realizarse desde Scheduling.
        """

        original_duration = (
            self.task.estimated_duration_days
        )

        response = self.client.patch(
            self.detail_url,
            {
                "estimated_duration_days": 8,
            },
            format="json",
        )

        # El CRUD debe rechazar el cambio.
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            response.data,
        )

        self.assertIn(
            "estimated_duration_days",
            response.data,
        )

        # Verificar que PostgreSQL no cambió.
        self.task.refresh_from_db()

        self.assertEqual(
            self.task.estimated_duration_days,
            original_duration,
        )

    def test_reject_negative_duration(self):
        response = self.client.patch(
            self.detail_url,
            {
                "estimated_duration_days": -3,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_create_task_with_original_fields(self):
        response = self.client.post(
            self.list_url,
            {
                "project": self.project.id,
                "name": "Actividad compatible",
                "description": "CRUD anterior",
                "status": "PENDING",
                "start_date": "2026-11-21",
                "end_date": "2026-11-25",
                "position": 2,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        self.assertEqual(
            response.data["progress_percent"],
            "0.00",
        )

    def test_reject_dates_outside_project(self):
        response = self.client.patch(
            self.detail_url,
            {
                "end_date": "2027-01-10",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_real_dates_can_differ_from_plan(self):
        response = self.client.patch(
            self.detail_url,
            {
                "actual_start_date": "2026-11-22",
                "actual_end_date": "2027-01-03",
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
            self.task.actual_end_date,
            date(2027, 1, 3),
        )
