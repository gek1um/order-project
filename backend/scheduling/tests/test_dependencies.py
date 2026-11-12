
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from projects.models import Project
from tasks.models import Task

from scheduling.models import TaskDependency


class TaskDependencyTests(TestCase):
    """
    Pruebas de integridad del modelo
    de dependencias temporales.
    """

    def setUp(self):
        self.project = Project.objects.create(
            code="SCH-001",
            name="Proyecto de programación",
            description="Pruebas de dependencias",
            manager_name="Administrador",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
            baseline_budget=Decimal("1000000.00"),
        )

        self.other_project = Project.objects.create(
            code="SCH-002",
            name="Otro proyecto",
            description="Proyecto independiente",
            manager_name="Administrador",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
            baseline_budget=Decimal("1000000.00"),
        )

        self.task_a = self.create_task("Tarea A", 1)
        self.task_b = self.create_task("Tarea B", 2)
        self.task_c = self.create_task("Tarea C", 3)
        self.task_d = self.create_task(
            "Tarea D",
            4,
            self.other_project,
        )

    def create_task(self, name, position, project=None):
        selected_project = project or self.project

        return Task.objects.create(
            project=selected_project,
            name=name,
            description="Actividad de prueba",
            status=Task.Status.PENDING,
            start_date=date(2026, 11, 2),
            end_date=date(2026, 11, 5),
            position=position,
        )

    def create_dependency(self, predecessor, successor):
        dependency = TaskDependency(
            predecessor=predecessor,
            successor=successor,
        )

        dependency.full_clean()
        dependency.save()

        return dependency

    def test_create_valid_dependency(self):
        self.create_dependency(
            self.task_a,
            self.task_b,
        )

        self.assertEqual(
            TaskDependency.objects.count(),
            1,
        )

    def test_reject_self_dependency(self):
        dependency = TaskDependency(
            predecessor=self.task_a,
            successor=self.task_a,
        )

        with self.assertRaises(ValidationError):
            dependency.full_clean()

    def test_reject_cross_project_dependency(self):
        dependency = TaskDependency(
            predecessor=self.task_a,
            successor=self.task_d,
        )

        with self.assertRaises(ValidationError):
            dependency.full_clean()

    def test_reject_duplicate_dependency(self):
        self.create_dependency(
            self.task_a,
            self.task_b,
        )

        duplicate = TaskDependency(
            predecessor=self.task_a,
            successor=self.task_b,
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_reject_direct_cycle(self):
        self.create_dependency(
            self.task_a,
            self.task_b,
        )

        reverse = TaskDependency(
            predecessor=self.task_b,
            successor=self.task_a,
        )

        with self.assertRaises(ValidationError):
            reverse.full_clean()

    def test_reject_indirect_cycle(self):
        self.create_dependency(
            self.task_a,
            self.task_b,
        )

        self.create_dependency(
            self.task_b,
            self.task_c,
        )

        circular = TaskDependency(
            predecessor=self.task_c,
            successor=self.task_a,
        )

        with self.assertRaises(ValidationError):
            circular.full_clean()

    def test_allow_multiple_predecessors(self):
        self.create_dependency(
            self.task_a,
            self.task_c,
        )

        self.create_dependency(
            self.task_b,
            self.task_c,
        )

        self.assertEqual(
            TaskDependency.objects.count(),
            2,
        )

    def test_update_dependency_without_cycle(self):
        dependency = self.create_dependency(
            self.task_a,
            self.task_b,
        )

        dependency.successor = self.task_c

        dependency.full_clean()
        dependency.save()

        dependency.refresh_from_db()

        self.assertEqual(
            dependency.successor_id,
            self.task_c.id,
        )

    def test_reject_cycle_when_editing(self):
        self.create_dependency(
            self.task_a,
            self.task_b,
        )

        self.create_dependency(
            self.task_b,
            self.task_c,
        )

        editable = self.create_dependency(
            self.task_a,
            self.task_c,
        )

        # Modificar A -> C por C -> A
        # cerraría el ciclo A -> B -> C -> A.
        editable.predecessor = self.task_c
        editable.successor = self.task_a

        with self.assertRaises(ValidationError):
            editable.full_clean()
