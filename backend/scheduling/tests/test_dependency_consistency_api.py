from django.contrib.auth import get_user_model
"""Pruebas de validación temporal de escrituras REST de dependencias."""
from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project
from tasks.models import Task
from scheduling.models import TaskDependency


class DependencyConsistencyAPITests(APITestCase):
    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code="CONS-DEP-001",
            name="Consistencia de dependencias",
            manager_name="QA",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 31),
            baseline_budget=Decimal("10000.00"),
        )
        self.a = self.make_task("A", 1, date(2026, 11, 13), date(2026, 11, 17), 3)
        self.b = self.make_task("B", 2, date(2026, 11, 18), date(2026, 11, 20), 3)
        self.c = self.make_task("C", 3, date(2026, 11, 23), date(2026, 11, 24), 2)
        self.list_url = reverse("task-dependency-list")

    def make_task(self, name, position, start, end, duration):
        return Task.objects.create(
            project=self.project, name=name, position=position,
            start_date=start, end_date=end, estimated_duration_days=duration,
        )

    def create(self, predecessor, successor, kind="FS", lag=0):
        return self.client.post(self.list_url, {
            "predecessor": predecessor.id,
            "successor": successor.id,
            "dependency_type": kind,
            "lag_days": lag,
        }, format="json")

    def detail(self, pk):
        return reverse("task-dependency-detail", args=[pk])

    def test_accept_valid_fs(self):
        response = self.create(self.a, self.b)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(TaskDependency.objects.count(), 1)

    def test_reject_fs_when_successor_starts_too_early(self):
        response = self.create(self.b, self.a)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("schedule_issues", response.data)
        self.assertEqual(TaskDependency.objects.count(), 0)

    def test_reject_positive_lag_when_unsatisfied(self):
        response = self.create(self.a, self.b, "FS", 2)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(TaskDependency.objects.count(), 0)

    def test_accept_multiple_predecessors(self):
        response1 = self.create(self.a, self.c)
        response2 = self.create(self.b, self.c)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED, response1.data)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED, response2.data)
        self.assertEqual(TaskDependency.objects.count(), 2)

    def test_reject_patch_and_rollback(self):
        created = self.create(self.a, self.b)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        pk = created.data["id"]
        changed = self.client.patch(self.detail(pk), {"lag_days": 3}, format="json")
        self.assertEqual(changed.status_code, status.HTTP_400_BAD_REQUEST, changed.data)
        dependency = TaskDependency.objects.get(pk=pk)
        self.assertEqual(dependency.lag_days, 0)
        self.assertEqual(dependency.dependency_type, "FS")

    def test_accept_patch_to_less_restrictive_lag(self):
        created = self.create(self.a, self.b)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        patched = self.client.patch(
            self.detail(created.data["id"]), {"lag_days": -1}, format="json"
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK, patched.data)
        self.assertEqual(TaskDependency.objects.get(pk=created.data["id"]).lag_days, -1)

    def test_reject_update_type_when_unsatisfied(self):
        created = self.create(self.a, self.b, "SS")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        changed = self.client.patch(self.detail(created.data["id"]), {
            "dependency_type": "FS", "lag_days": 3,
        }, format="json")
        self.assertEqual(changed.status_code, status.HTTP_400_BAD_REQUEST, changed.data)
        dependency = TaskDependency.objects.get(pk=created.data["id"])
        self.assertEqual(dependency.dependency_type, "SS")
        self.assertEqual(dependency.lag_days, 0)

    def test_reject_nonworking_predecessor_boundary(self):
        self.a.end_date = date(2026, 11, 15)  # domingo, dato legado inconsistente
        self.a.save()
        response = self.create(self.a, self.b, "FS")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(TaskDependency.objects.count(), 0)

    def test_unrelated_legacy_warning_does_not_block(self):
        self.c.estimated_duration_days = None
        self.c.save()
        response = self.create(self.a, self.b)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_delete_existing_dependency(self):
        created = self.create(self.a, self.b)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        response = self.client.delete(self.detail(created.data["id"]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(TaskDependency.objects.count(), 0)
