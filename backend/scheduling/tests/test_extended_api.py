from django.contrib.auth import get_user_model

from datetime import date
from decimal import Decimal

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project
from tasks.models import Task
from scheduling.models import TaskDependency


class ExtendedDependencyAPITests(APITestCase):
    """
    Pruebas para los cuatro tipos de dependencias
    y los desfases positivos y negativos.
    """

    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code="SCH-EXT-001",
            name="Proyecto de dependencias extendidas",
            description="Prueba de tipos y desfases",
            manager_name="Responsable QA",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000000.00"),
        )

        self.task_a = self.create_task("Tarea A", 1)
        self.task_b = self.create_task("Tarea B", 2)

        self.url = reverse("task-dependency-list")

    def create_task(self, name, position):
        return Task.objects.create(
            project=self.project,
            name=name,
            description="Prueba temporal",
            status=Task.Status.PENDING,
            start_date=(
                date(2026, 11, 10) if position == 1
                else date(2026, 11, 13)
            ),
            end_date=(
                date(2026, 11, 12) if position == 1
                else date(2026, 11, 17)
            ),
            position=position,
        )

    def send_dependency(self, dependency_type, lag_days=0):
        return self.client.post(
            self.url,
            {
                "predecessor": self.task_a.id,
                "successor": self.task_b.id,
                "dependency_type": dependency_type,
                "lag_days": lag_days,
            },
            format="json",
        )

    def test_finish_to_start(self):
        response = self.send_dependency("FS")

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

    def test_start_to_start(self):
        response = self.send_dependency("SS", 2)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        self.assertEqual(response.data["lag_days"], 2)

    def test_finish_to_finish(self):
        response = self.send_dependency("FF", -1)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        self.assertEqual(response.data["lag_days"], -1)

    def test_start_to_finish(self):
        response = self.send_dependency("SF")

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

    def test_reject_unknown_dependency_type(self):
        response = self.send_dependency("XX")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_update_lag_days(self):
        created = self.send_dependency("FS")

        self.assertEqual(
            created.status_code,
            status.HTTP_201_CREATED,
        )

        detail_url = reverse(
            "task-dependency-detail",
            args=[created.data["id"]],
        )

        response = self.client.patch(
            detail_url,
            {"lag_days": -3},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        dependency = TaskDependency.objects.get(
            id=created.data["id"],
        )

        self.assertEqual(dependency.lag_days, -3)

    def test_reject_non_integer_lag(self):
        response = self.send_dependency("FS", "abc")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
