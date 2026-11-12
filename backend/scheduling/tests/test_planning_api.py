from django.contrib.auth import get_user_model

from datetime import date
from decimal import Decimal

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project
from tasks.models import Task
from scheduling.models import TaskDependency


class PlanningAPITests(APITestCase):

    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code="PLAN-API-001",
            name="Proyecto de planificación API",
            description="Pruebas de propagación REST",
            manager_name="Responsable QA",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000000.00"),
        )

        self.a = self.create_task(
            "Diseño",
            date(2026, 11, 13),
            date(2026, 11, 17),
            3,
            1,
        )

        self.b = self.create_task(
            "Desarrollo",
            date(2026, 11, 18),
            date(2026, 11, 20),
            3,
            2,
        )

        self.c = self.create_task(
            "Pruebas",
            date(2026, 11, 23),
            date(2026, 11, 24),
            2,
            3,
        )

        self.create_dependency(self.a, self.b)
        self.create_dependency(self.b, self.c)

        self.preview_url = reverse(
            "task-schedule-preview",
            args=[self.a.id],
        )

        self.reschedule_url = reverse(
            "task-schedule-reschedule",
            args=[self.a.id],
        )

        self.schedule_url = reverse(
            "project-schedule",
            args=[self.project.id],
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
    ):
        dependency = TaskDependency(
            predecessor=predecessor,
            successor=successor,
            dependency_type="FS",
            lag_days=0,
        )

        dependency.full_clean()
        dependency.save()

    def request_body(self, duration=5):
        return {
            "start_date": "2026-11-13",
            "duration_days": duration,
        }

    def refresh_tasks(self):
        self.a.refresh_from_db()
        self.b.refresh_from_db()
        self.c.refresh_from_db()

    # ======================================
    # SIMULACIÓN
    # ======================================

    def test_preview_returns_calculated_changes(self):
        response = self.client.post(
            self.preview_url,
            self.request_body(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertFalse(
            response.data["committed"]
        )

        self.assertEqual(
            response.data["updated_tasks"],
            3,
        )

        self.assertEqual(
            len(response.data["changes"]),
            3,
        )

    def test_preview_does_not_save(self):
        self.client.post(
            self.preview_url,
            self.request_body(),
            format="json",
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

    # ======================================
    # REPROGRAMACIÓN
    # ======================================

    def test_reschedule_saves_changes(self):
        response = self.client.post(
            self.reschedule_url,
            self.request_body(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertTrue(
            response.data["committed"]
        )

        self.assertEqual(
            response.data["updated_tasks"],
            3,
        )

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
            self.c.start_date,
            date(2026, 11, 25),
        )

    def test_reschedule_returns_new_dates(self):
        response = self.client.post(
            self.reschedule_url,
            self.request_body(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        changes = {
            item["task_id"]: item
            for item in response.data["changes"]
        }

        self.assertEqual(
            changes[self.a.id]["new_end_date"],
            "2026-11-19",
        )

        self.assertEqual(
            changes[self.b.id]["new_start_date"],
            "2026-11-20",
        )

        self.assertEqual(
            changes[self.c.id]["new_start_date"],
            "2026-11-25",
        )

    def test_no_changes_when_schedule_is_same(self):
        response = self.client.post(
            self.reschedule_url,
            self.request_body(duration=3),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(
            response.data["updated_tasks"],
            0,
        )

    # ======================================
    # VALIDACIONES DE ENTRADA
    # ======================================

    def test_reject_missing_duration(self):
        response = self.client.post(
            self.preview_url,
            {
                "start_date": "2026-11-13",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "duration_days",
            response.data,
        )

    def test_reject_zero_duration(self):
        response = self.client.post(
            self.preview_url,
            self.request_body(duration=0),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_reject_weekend_start(self):
        response = self.client.post(
            self.preview_url,
            {
                "start_date": "2026-11-14",
                "duration_days": 3,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    # ======================================
    # PROTECCIÓN DE DATOS
    # ======================================

    def test_reject_moving_started_successor(self):
        self.b.status = Task.Status.IN_PROGRESS

        self.b.actual_start_date = date(
            2026, 11, 18
        )

        self.b.save()

        response = self.client.post(
            self.reschedule_url,
            self.request_body(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            response.data,
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

    def test_reject_schedule_beyond_project_end(self):
        self.project.end_date = date(
            2026, 11, 25
        )

        self.project.save()

        response = self.client.post(
            self.reschedule_url,
            self.request_body(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            response.data,
        )

        self.refresh_tasks()

        self.assertEqual(
            self.a.end_date,
            date(2026, 11, 17),
        )

        self.assertEqual(
            self.c.end_date,
            date(2026, 11, 24),
        )

    # ======================================
    # CONSULTA DEL CRONOGRAMA
    # ======================================

    def test_get_project_schedule(self):
        response = self.client.get(
            self.schedule_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        self.assertEqual(
            response.data["tasks_count"],
            3,
        )

        self.assertEqual(
            response.data["dependencies_count"],
            2,
        )

        self.assertEqual(
            response.data["calendar"]["source"],
            "default",
        )

    def test_schedule_reflects_rescheduling(self):
        self.client.post(
            self.reschedule_url,
            self.request_body(),
            format="json",
        )

        response = self.client.get(
            self.schedule_url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        tasks = {
            task["id"]: task
            for task in response.data["tasks"]
        }

        self.assertEqual(
            tasks[self.a.id]["end_date"],
            date(2026, 11, 19),
        )

        self.assertEqual(
            tasks[self.c.id]["start_date"],
            date(2026, 11, 25),
        )


    # ======================================
    # RECURSOS INEXISTENTES
    # ======================================

    def test_reject_nonexistent_task(self):
        url = reverse(
            "task-schedule-preview",
            args=[999999],
        )

        response = self.client.post(
            url,
            self.request_body(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_reject_nonexistent_project(self):
        url = reverse(
            "project-schedule",
            args=[999999],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
