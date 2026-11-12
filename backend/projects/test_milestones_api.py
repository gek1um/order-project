from django.contrib.auth import get_user_model
from datetime import date
from django.urls import reverse
from rest_framework.test import APITestCase
from projects.models import Project, Milestone


class MilestoneApiTests(APITestCase):
    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code='HITOS-01', name='Proyecto con hitos', manager_name='Responsable',
            start_date=date(2026, 11, 1), end_date=date(2026, 11, 30),
        )
        self.other = Project.objects.create(
            code='HITOS-02', name='Otro proyecto', manager_name='Responsable',
            start_date=date(2026, 12, 1), end_date=date(2026, 12, 31),
        )
        self.url = reverse('milestone-list')
        self.payload = {
            'project': self.project.pk, 'name': 'Recepción conforme',
            'due_date': '2026-11-18', 'responsible': 'Jefa de proyecto',
            'acceptance_criteria': 'Acta firmada', 'status': 'PENDING',
            'evidence': '', 'completed_at': None,
        }

    def create(self):
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def test_create_and_filter(self):
        pk = self.create()
        result = self.client.get(self.url, {'project': self.project.pk})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0]['id'], pk)
        empty = self.client.get(self.url, {'project': self.other.pk})
        self.assertEqual(len(empty.data), 0)

    def test_reject_outside_project(self):
        payload = {**self.payload, 'due_date': '2026-12-03'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Milestone.objects.exists())

    def test_completion_requires_date_and_evidence(self):
        pk = self.create()
        detail = reverse('milestone-detail', args=[pk])
        response = self.client.patch(detail, {'status': 'COMPLETED'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Milestone.objects.get(pk=pk).status, 'PENDING')

    def test_complete_with_evidence(self):
        pk = self.create()
        response = self.client.patch(reverse('milestone-detail', args=[pk]), {
            'status': 'COMPLETED', 'completed_at': '2026-11-19',
            'evidence': 'Acta N° 15 aprobada',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Milestone.objects.get(pk=pk).status, 'COMPLETED')

    def test_reject_project_reassignment(self):
        pk = self.create()
        response = self.client.patch(reverse('milestone-detail', args=[pk]), {
            'project': self.other.pk,
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_project_shrink_rejected(self):
        self.create()
        response = self.client.patch(reverse('project-detail', args=[self.project.pk]), {
            'end_date': '2026-11-10',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.project.refresh_from_db()
        self.assertEqual(self.project.end_date, date(2026, 11, 30))

    def test_delete(self):
        pk = self.create()
        response = self.client.delete(reverse('milestone-detail', args=[pk]))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Milestone.objects.filter(pk=pk).exists())

    def test_pending_cannot_have_completed_at(self):
        response = self.client.post(self.url, {**self.payload, 'completed_at': '2026-11-19'}, format='json')
        self.assertEqual(response.status_code, 400)
