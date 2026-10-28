
from datetime import date
from decimal import Decimal

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project
from .models import Task


class TaskAPITests(APITestCase):

    def setUp(self):
        self.project = Project.objects.create(
            code="PRJ-TEST-001",
            name="Proyecto de pruebas",
            description="Proyecto para pruebas de API",
            manager_name="Administrador",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
            baseline_budget=Decimal("1000000.00"),
        )

        self.list_url = reverse("task-list")

    def task_data(self, **overrides):
        data = {
            "project": self.project.id,
            "name": "Actividad de prueba",
            "description": "Descripción de prueba",
            "status": "PENDING",
            "start_date": "2026-11-03",
            "end_date": "2026-11-07",
            "position": 1,
        }

        data.update(overrides)
        return data

    def create_task(self):
        return Task.objects.create(
            project=self.project,
            name="Actividad existente",
            description="Actividad de prueba",
            status=Task.Status.PENDING,
            start_date=date(2026, 11, 3),
            end_date=date(2026, 11, 7),
            position=1,
        )

    def test_create_task_successfully(self):
        response = self.client.post(
            self.list_url,
            self.task_data(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(Task.objects.count(), 1)

    def test_reject_invalid_dates(self):
        response = self.client.post(
            self.list_url,
            self.task_data(
                start_date="2026-11-20",
                end_date="2026-11-10",
            ),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_reject_dates_outside_project(self):
        response = self.client.post(
            self.list_url,
            self.task_data(
                start_date="2026-12-01",
                end_date="2026-12-05",
            ),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_reject_nonexistent_project(self):
        response = self.client.post(
            self.list_url,
            self.task_data(project=999999),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_filter_tasks_by_project(self):
        self.create_task()

        response = self.client.get(
            self.list_url,
            {"project": self.project.id},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(len(response.data), 1)

    def test_update_task_status(self):
        task = self.create_task()

        response = self.client.patch(
            reverse("task-detail", args=[task.id]),
            {"status": "IN_PROGRESS"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        task.refresh_from_db()

        self.assertEqual(
            task.status,
            Task.Status.IN_PROGRESS,
        )

    def test_reject_project_date_conflict(self):
        self.create_task()

        response = self.client.patch(
            reverse(
                "project-detail",
                args=[self.project.id],
            ),
            {"end_date": "2026-11-04"},
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
