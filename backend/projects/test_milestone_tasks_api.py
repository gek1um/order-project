from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from core.models import ProjectMembership
from projects.models import Milestone, Project
from tasks.models import Task


class MilestoneTasksApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username='admin_milestone_82', email='admin82@example.test', password='SafePass123!'
        )
        self.member = User.objects.create_user(
            username='member_milestone_82', password='SafePass123!'
        )
        self.outsider = User.objects.create_user(
            username='outsider_milestone_82', password='SafePass123!'
        )
        self.project = Project.objects.create(
            code='HITO-821A', name='Proyecto A', manager_name='Responsable',
            start_date=date(2026, 11, 1), end_date=date(2026, 11, 30),
        )
        self.other_project = Project.objects.create(
            code='HITO-821B', name='Proyecto B', manager_name='Responsable',
            start_date=date(2026, 11, 1), end_date=date(2026, 11, 30),
        )
        ProjectMembership.objects.create(user=self.member, project=self.project)
        self.first = self.make_task(self.project, 'Analisis')
        self.second = self.make_task(self.project, 'Construccion')
        self.foreign = self.make_task(self.other_project, 'Secreto')
        self.url = reverse('milestone-list')
        self.payload = {
            'project': self.project.pk, 'name': 'Entrega verificada',
            'due_date': '2026-11-20', 'responsible': 'Lider',
            'acceptance_criteria': 'Acta aprobada', 'status': 'PENDING',
            'tasks': [self.first.pk, self.second.pk],
        }

    @staticmethod
    def make_task(project, name):
        return Task.objects.create(
            project=project, name=name,
            start_date=date(2026, 11, 3), end_date=date(2026, 11, 4),
        )

    def authenticate_admin(self):
        self.client.force_authenticate(user=self.admin)

    def test_admin_creates_hito_with_multiple_tasks(self):
        self.authenticate_admin()
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        milestone = Milestone.objects.get(pk=response.data['id'])
        self.assertEqual(set(milestone.tasks.values_list('pk', flat=True)), {self.first.pk, self.second.pk})
        self.assertEqual(set(response.data['tasks']), {self.first.pk, self.second.pk})

    def test_admin_rejects_task_from_other_project(self):
        self.authenticate_admin()
        payload = {**self.payload, 'tasks': [self.first.pk, self.foreign.pk]}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Milestone.objects.exists())

    def test_patch_replaces_associations_without_changing_hito(self):
        self.authenticate_admin()
        created = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        response = self.client.patch(
            reverse('milestone-detail', args=[created.data['id']]),
            {'tasks': [self.second.pk]}, format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['tasks'], [self.second.pk])
        self.assertEqual(response.data['name'], self.payload['name'])

    def test_patch_invalid_tasks_preserves_original_associations(self):
        self.authenticate_admin()
        created = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        response = self.client.patch(
            reverse('milestone-detail', args=[created.data['id']]),
            {'tasks': [self.foreign.pk]}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        milestone = Milestone.objects.get(pk=created.data['id'])
        self.assertEqual(set(milestone.tasks.values_list('pk', flat=True)), {self.first.pk, self.second.pk})

    def test_empty_tasks_is_compatible_with_existing_hitos(self):
        self.authenticate_admin()
        payload = {key: value for key, value in self.payload.items() if key != 'tasks'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['tasks'], [])

    def test_completed_hito_retains_tasks(self):
        self.authenticate_admin()
        created = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        response = self.client.patch(
            reverse('milestone-detail', args=[created.data['id']]),
            {'status': 'COMPLETED', 'completed_at': '2026-11-21', 'evidence': 'Acta'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(set(response.data['tasks']), {self.first.pk, self.second.pk})

    def test_project_user_can_associate_own_tasks(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_project_user_cannot_reference_foreign_task(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.post(
            self.url, {**self.payload, 'tasks': [self.foreign.pk]}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Milestone.objects.exists())

    def test_user_without_membership_cannot_create(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Milestone.objects.exists())

    def test_anonymous_is_denied(self):
        response = self.client.get(self.url)
        self.assertIn(response.status_code, [401, 403])
