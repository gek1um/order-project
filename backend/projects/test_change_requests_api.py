from django.contrib.auth import get_user_model
from datetime import date
from decimal import Decimal
from rest_framework.test import APITestCase
from .models import Project
from .change_models import ChangeEvent, ChangeRequest


class ChangeRequestAPITests(APITestCase):
    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code='CHANGE-1', name='Control cambios', manager_name='Jefa proyecto',
            start_date=date(2026, 11, 1), end_date=date(2026, 12, 31),
            baseline_budget=Decimal('1000000'),
        )
        self.other = Project.objects.create(
            code='CHANGE-2', name='Otro proyecto', manager_name='Otra jefa',
            start_date=date(2026, 11, 1), end_date=date(2026, 12, 31),
        )
        self.url = '/api/change-requests/'

    def payload(self, **kwargs):
        return dict(project=self.project.pk, title='Nueva integración', requester='Analista',
                    requested_at='2026-11-11', description='Agregar integración de reportes',
                    justification='Necesidad del cliente', kind='SCOPE', priority='HIGH',
                    estimated_cost='80000.00', estimated_delay_days=3,
                    responsible='Equipo técnico', **kwargs)

    def create(self):
        response = self.client.post(self.url, self.payload(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def submit(self, pk):
        return self.client.post(f'{self.url}{pk}/submit/', {'actor': 'Analista'}, format='json')

    def test_create_and_event(self):
        pk = self.create()
        change = ChangeRequest.objects.get(pk=pk)
        self.assertEqual(change.status, 'OPEN')
        self.assertEqual(ChangeEvent.objects.filter(change_request=change).count(), 1)

    def test_filter_project_and_status(self):
        self.create()
        response = self.client.get(self.url, {'project': self.project.pk, 'status': 'OPEN'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(self.client.get(self.url, {'project': 'oops'}).status_code, 400)

    def test_edit_open_and_event(self):
        pk = self.create()
        response = self.client.patch(f'{self.url}{pk}/', {'title': 'Ajuste'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(ChangeEvent.objects.filter(change_request_id=pk).count(), 2)

    def test_project_immutable(self):
        pk = self.create()
        response = self.client.patch(f'{self.url}{pk}/', {'project': self.other.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ChangeRequest.objects.get(pk=pk).project_id, self.project.pk)

    def test_negative_cost_rejected(self):
        data = self.payload()
        data['estimated_cost'] = '-1'
        self.assertEqual(self.client.post(self.url, data, format='json').status_code, 400)

    def test_submit_and_audit(self):
        pk = self.create()
        response = self.submit(pk)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'UNDER_REVIEW')
        self.assertEqual(len(response.data['events']), 2)

    def test_repeated_submit_rejected(self):
        pk = self.create()
        self.submit(pk)
        self.assertEqual(self.submit(pk).status_code, 409)
        self.assertEqual(ChangeEvent.objects.filter(change_request_id=pk).count(), 2)

    def test_approve_with_reason_and_actor(self):
        pk = self.create()
        self.submit(pk)
        response = self.client.post(f'{self.url}{pk}/approve/',
                                    {'actor': 'Directora', 'reason': 'Impacto aceptable'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'APPROVED')
        self.assertEqual(response.data['decided_by'], 'test_admin_813')
        self.assertEqual(ChangeEvent.objects.filter(change_request_id=pk).count(), 3)

    def test_reject_with_reason(self):
        pk = self.create()
        self.submit(pk)
        response = self.client.post(f'{self.url}{pk}/reject/',
                                    {'actor': 'Directora', 'reason': 'Costo excesivo'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(ChangeRequest.objects.get(pk=pk).status, 'REJECTED')

    def test_decision_requires_reason(self):
        pk = self.create()
        self.submit(pk)
        self.assertEqual(self.client.post(f'{self.url}{pk}/approve/',
                                          {'actor': 'Directora'}, format='json').status_code, 400)
        self.assertEqual(ChangeRequest.objects.get(pk=pk).status, 'UNDER_REVIEW')

    def test_edit_reviewing_rejected(self):
        pk = self.create()
        self.submit(pk)
        self.assertEqual(self.client.patch(f'{self.url}{pk}/',
                                           {'title': 'Prohibido'}, format='json').status_code, 400)

    def test_approve_does_not_change_project_budget(self):
        pk = self.create()
        self.submit(pk)
        self.client.post(f'{self.url}{pk}/approve/',
                         {'actor': 'Directora', 'reason': 'Aprobado'}, format='json')
        self.project.refresh_from_db()
        self.assertEqual(self.project.baseline_budget, Decimal('1000000'))

    def test_delete_preserves_history(self):
        pk = self.create()
        self.assertEqual(self.client.delete(f'{self.url}{pk}/').status_code, 405)
        self.assertTrue(ChangeRequest.objects.filter(pk=pk).exists())

    def test_read_only_status_and_decision(self):
        pk = self.create()
        response = self.client.patch(f'{self.url}{pk}/', {'status': 'APPROVED', 'decided_by': 'X'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'OPEN')
        self.assertEqual(response.data['decided_by'], '')
