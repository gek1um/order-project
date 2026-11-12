from django.contrib.auth import get_user_model

from datetime import date
from decimal import Decimal

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project
from tasks.models import Task


class ProjectIntegrationTests(APITestCase):
    """
    Pruebas de integración de Projects y Tasks.

    Comprueba:
    - Operaciones CRUD.
    - Validaciones de fechas.
    - Presupuesto inicial inmutable.
    - Relaciones entre proyectos y tareas.
    - Restricciones de eliminación.
    - Persistencia de datos.
    """

    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        """
        Crea datos independientes para cada prueba.
        """

        self.project = Project.objects.create(
            code="PRJ-INT-001",
            name="Proyecto de integración",
            description="Proyecto para pruebas integrales",
            manager_name="Administrador QA",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
            baseline_budget=Decimal("1000000.00"),
        )

        self.other_project = Project.objects.create(
            code="PRJ-INT-002",
            name="Segundo proyecto",
            description="Proyecto de control",
            manager_name="Administrador QA",
            status=Project.Status.IN_PROGRESS,
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 31),
            baseline_budget=Decimal("2000000.00"),
        )

        self.projects_url = reverse("project-list")
        self.tasks_url = reverse("task-list")

    # ----------------------------------------------
    # HELPERS
    # ----------------------------------------------

    def project_detail_url(self, project_id):
        return reverse(
            "project-detail",
            args=[project_id],
        )

    def task_detail_url(self, task_id):
        return reverse(
            "task-detail",
            args=[task_id],
        )

    def create_task(self, project=None):
        """
        Crea una tarea de prueba dentro del proyecto.
        """

        selected_project = project or self.project

        return Task.objects.create(
            project=selected_project,
            name="Actividad de integración",
            description="Actividad para validar relaciones",
            status=Task.Status.PENDING,
            start_date=selected_project.start_date,
            end_date=selected_project.start_date,
            position=1,
        )

    def valid_project_payload(self):
        return {
            "code": "PRJ-INT-003",
            "name": "Proyecto creado desde API",
            "description": "Validación de creación REST",
            "manager_name": "Responsable QA",
            "status": "PLANNED",
            "start_date": "2027-01-01",
            "end_date": "2027-01-31",
            "baseline_budget": "3000000.00",
        }

    # ----------------------------------------------
    # TEST 1 - CREAR PROYECTO
    # ----------------------------------------------

    def test_create_project_successfully(self):
        response = self.client.post(
            self.projects_url,
            self.valid_project_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            Project.objects.filter(
                code="PRJ-INT-003",
            ).exists()
        )

    # ----------------------------------------------
    # TEST 2 - CONSULTAR PROYECTO
    # ----------------------------------------------

    def test_get_project_by_id(self):
        response = self.client.get(
            self.project_detail_url(self.project.id)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["code"],
            "PRJ-INT-001",
        )

    # ----------------------------------------------
    # TEST 3 - ACTUALIZAR PROYECTO
    # ----------------------------------------------

    def test_update_project_successfully(self):
        response = self.client.patch(
            self.project_detail_url(self.project.id),
            {
                "name": "Proyecto actualizado",
                "status": "IN_PROGRESS",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.project.refresh_from_db()

        self.assertEqual(
            self.project.name,
            "Proyecto actualizado",
        )

        self.assertEqual(
            self.project.status,
            Project.Status.IN_PROGRESS,
        )

    # ----------------------------------------------
    # TEST 4 - PRESUPUESTO INMUTABLE
    # ----------------------------------------------

    def test_reject_baseline_budget_change(self):
        response = self.client.patch(
            self.project_detail_url(self.project.id),
            {
                "baseline_budget": "1500000.00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.project.refresh_from_db()

        self.assertEqual(
            self.project.baseline_budget,
            Decimal("1000000.00"),
        )

    # ----------------------------------------------
    # TEST 5 - FECHAS INCORRECTAS
    # ----------------------------------------------

    def test_reject_invalid_project_dates(self):
        response = self.client.patch(
            self.project_detail_url(self.project.id),
            {
                "start_date": "2026-12-20",
                "end_date": "2026-11-10",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.project.refresh_from_db()

        self.assertEqual(
            self.project.start_date,
            date(2026, 11, 1),
        )

    # ----------------------------------------------
    # TEST 6 - FECHAS VS TAREAS
    # ----------------------------------------------

    def test_reject_dates_excluding_existing_tasks(self):
        Task.objects.create(
            project=self.project,
            name="Actividad al final del período",
            description="Prueba de integridad temporal",
            status=Task.Status.PENDING,
            start_date=date(2026, 11, 20),
            end_date=date(2026, 11, 25),
            position=1,
        )

        response = self.client.patch(
            self.project_detail_url(self.project.id),
            {
                "end_date": "2026-11-15",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.project.refresh_from_db()

        self.assertEqual(
            self.project.end_date,
            date(2026, 11, 30),
        )

    # ----------------------------------------------
    # TEST 7 - PROTEGER PROYECTOS CON TAREAS
    # ----------------------------------------------

    def test_reject_delete_project_with_tasks(self):
        self.create_task()

        response = self.client.delete(
            self.project_detail_url(self.project.id)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

        self.assertTrue(
            Project.objects.filter(
                id=self.project.id,
            ).exists()
        )

        self.assertEqual(
            Task.objects.filter(
                project=self.project,
            ).count(),
            1,
        )

    # ----------------------------------------------
    # TEST 8 - ELIMINAR PROYECTO SIN TAREAS
    # ----------------------------------------------

    def test_delete_project_without_tasks(self):
        project_id = self.project.id

        response = self.client.delete(
            self.project_detail_url(project_id)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            Project.objects.filter(
                id=project_id,
            ).exists()
        )

    # ----------------------------------------------
    # TEST 9 - FILTRAR PROYECTOS
    # ----------------------------------------------

    def test_filter_projects_by_status(self):
        response = self.client.get(
            self.projects_url,
            {
                "status": "PLANNED",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        codes = [
            project["code"]
            for project in response.data
        ]

        self.assertIn(
            "PRJ-INT-001",
            codes,
        )

        self.assertNotIn(
            "PRJ-INT-002",
            codes,
        )

    # ----------------------------------------------
    # TEST 10 - AISLAMIENTO ENTRE PROYECTOS
    # ----------------------------------------------

    def test_tasks_belong_to_correct_project(self):
        self.create_task(self.project)
        self.create_task(self.other_project)

        response = self.client.get(
            self.tasks_url,
            {
                "project": self.project.id,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["project"],
            self.project.id,
        )

    # ----------------------------------------------
    # TEST 11 - IMPEDIR REASIGNACIÓN
    # ----------------------------------------------

    def test_reject_task_project_reassignment(self):
        task = self.create_task()

        response = self.client.patch(
            self.task_detail_url(task.id),
            {
                "project": self.other_project.id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        task.refresh_from_db()

        self.assertEqual(
            task.project_id,
            self.project.id,
        )

    # ----------------------------------------------
    # TEST 12 - PERSISTENCIA
    # ----------------------------------------------

    def test_project_update_persists_in_database(self):
        response = self.client.patch(
            self.project_detail_url(self.project.id),
            {
                "manager_name": "Nuevo responsable",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        saved_project = Project.objects.get(
            id=self.project.id,
        )

        self.assertEqual(
            saved_project.manager_name,
            "Nuevo responsable",
        )
