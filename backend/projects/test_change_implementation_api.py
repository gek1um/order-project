from django.contrib.auth import get_user_model
from datetime import date
from decimal import Decimal

from rest_framework.test import APITestCase

from .change_models import ChangeApplication, ChangeEvent, ChangeRequest
from .models import Project
from tasks.models import Task


class ChangeImplementationAPITests(APITestCase):
    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code='CHANGE62-A', name='Proyecto con cambios', manager_name='PM',
            start_date=date(2026, 11, 2), end_date=date(2026, 12, 31),
            baseline_budget=Decimal('1000000.00'),
        )
        self.other = Project.objects.create(
            code='CHANGE62-B', name='Proyecto externo', manager_name='PM2',
            start_date=date(2026, 11, 2), end_date=date(2026, 12, 31),
        )
        self.task = Task.objects.create(
            project=self.project, name='Actividad', status=Task.Status.PENDING,
            start_date=date(2026, 11, 16), end_date=date(2026, 11, 18),
            estimated_duration_days=3,
        )
        self.other_task = Task.objects.create(
            project=self.other, name='No pertenece',
            start_date=date(2026, 11, 16), end_date=date(2026, 11, 18),
            estimated_duration_days=3,
        )
        self.change = ChangeRequest.objects.create(
            project=self.project, title='Ajuste cronograma', requester='Analista',
            requested_at=date(2026, 11, 11), description='Cambiar fechas',
            justification='Solicitud formal', kind='TIME',
            responsible='Responsable del cambio', estimated_cost=Decimal('100.00'),
            status=ChangeRequest.Status.APPROVED,
        )
        self.base = f'/api/change-requests/{self.change.pk}/'

    def post(self, action, data):
        return self.client.post(self.base + action + '/', data, format='json')

    def start(self):
        return self.post('start-implementation', {'actor': 'PM', 'committed_date': '2026-11-30'})

    def plan(self, **extra):
        return dict(actor='PM', task_id=self.task.pk,
                    start_date='2026-11-18', duration_days=3, **extra)

    def test_start_approved_and_event(self):
        response = self.start()
        self.assertEqual(response.status_code, 200, response.data)
        self.change.refresh_from_db()
        self.assertEqual(self.change.status, 'IMPLEMENTING')
        self.assertEqual(self.change.committed_date, date(2026, 11, 30))
        self.assertTrue(ChangeEvent.objects.filter(change_request=self.change, action='IMPLEMENTING').exists())

    def test_start_twice_is_rejected(self):
        self.assertEqual(self.start().status_code, 200)
        self.assertEqual(self.start().status_code, 400)

    def test_schedule_preview_without_writes(self):
        response = self.post('preview-schedule', self.plan())
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['committed'])
        self.task.refresh_from_db()
        self.assertEqual(self.task.start_date, date(2026, 11, 16))
        self.assertFalse(ChangeApplication.objects.exists())

    def test_apply_requires_implementation(self):
        response = self.post('apply-schedule', self.plan())
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(ChangeApplication.objects.exists())

    def test_apply_schedule_records_before_after(self):
        self.start()
        response = self.post('apply-schedule', self.plan())
        self.assertEqual(response.status_code, 200, response.data)
        self.task.refresh_from_db()
        self.assertEqual(self.task.start_date, date(2026, 11, 18))
        self.assertEqual(self.task.end_date, date(2026, 11, 20))
        row = ChangeApplication.objects.get(change_request=self.change)
        self.assertEqual(row.before['start_date'], '2026-11-16')
        self.assertEqual(row.after['end_date'], '2026-11-20')
        self.assertEqual(row.task_id, self.task.pk)
        self.assertEqual(response.data['change_request']['applications'][0]['kind'], 'SCHEDULE')

    def test_foreign_project_task_rejected(self):
        self.start()
        response = self.post('apply-schedule', dict(actor='PM', task_id=self.other_task.pk,
                                                    start_date='2026-11-18', duration_days=3))
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(ChangeApplication.objects.exists())

    def test_invalid_reprogramming_is_atomic(self):
        self.start()
        response = self.post('apply-schedule', dict(actor='PM', task_id=self.task.pk,
                                                    start_date='2027-01-10', duration_days=3))
        self.assertEqual(response.status_code, 400, response.data)
        self.task.refresh_from_db()
        self.assertEqual(self.task.start_date, date(2026, 11, 16))
        self.assertEqual(ChangeApplication.objects.count(), 0)
        self.assertFalse(ChangeEvent.objects.filter(action='SCHEDULE_APPLIED').exists())

    def test_record_cost_keeps_baseline(self):
        self.start()
        response = self.post('record-actual-cost', {'actor': 'PM', 'actual_cost': '900.00'})
        self.assertEqual(response.status_code, 200, response.data)
        self.change.refresh_from_db()
        self.project.refresh_from_db()
        self.assertEqual(self.change.actual_cost, Decimal('900.00'))
        self.assertEqual(self.project.baseline_budget, Decimal('1000000.00'))
        self.assertEqual(ChangeApplication.objects.get().kind, 'COST')

    def test_negative_cost_rejected(self):
        self.start()
        response = self.post('record-actual-cost', {'actor': 'PM', 'actual_cost': '-2.00'})
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(ChangeApplication.objects.exists())

    def test_close_requires_an_execution(self):
        self.start()
        response = self.post('close', {'actor': 'PM', 'actual_completion_date': '2026-11-25',
                                       'result': 'Entregado'})
        self.assertEqual(response.status_code, 400, response.data)
        self.change.refresh_from_db()
        self.assertEqual(self.change.status, 'IMPLEMENTING')

    def test_close_after_cost_and_prevent_more_writes(self):
        self.start()
        self.post('record-actual-cost', {'actor': 'PM', 'actual_cost': '120.00'})
        response = self.post('close', {'actor': 'PM', 'actual_completion_date': '2026-11-25',
                                       'result': 'Cambio entregado'})
        self.assertEqual(response.status_code, 200, response.data)
        self.change.refresh_from_db()
        self.assertEqual(self.change.status, 'CLOSED')
        self.assertEqual(self.change.result, 'Cambio entregado')
        self.assertEqual(self.post('close', {'actor': 'PM', 'actual_completion_date': '2026-11-25',
                                             'result': 'Duplicado'}).status_code, 400)
        self.assertEqual(self.post('record-actual-cost', {'actor': 'PM', 'actual_cost': '130.00'}).status_code, 400)
        self.assertTrue(ChangeEvent.objects.filter(action='CLOSED').exists())

    def test_close_before_request_date_rejected(self):
        self.start()
        self.post('record-actual-cost', {'actor': 'PM', 'actual_cost': '120.00'})
        response = self.post('close', {'actor': 'PM', 'actual_completion_date': '2026-11-01',
                                       'result': 'Inválido'})
        self.assertEqual(response.status_code, 400, response.data)
