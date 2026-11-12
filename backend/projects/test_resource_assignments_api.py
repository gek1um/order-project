from django.contrib.auth import get_user_model
from datetime import date
from decimal import Decimal

from rest_framework.test import APITestCase

from tasks.models import Task
from .models import Project
from .resource_models import Resource
from .resource_assignment_models import TaskResourceAssignment


class TaskResourceAssignmentAPITests(APITestCase):
    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code='COST-1', name='Proyecto costos', manager_name='Responsable',
            start_date=date(2026, 11, 2), end_date=date(2026, 12, 31),
            baseline_budget=Decimal('100000.00'),
        )
        self.other = Project.objects.create(
            code='COST-2', name='Otro proyecto', manager_name='Responsable',
            start_date=date(2026, 11, 2), end_date=date(2026, 12, 31),
        )
        self.task = Task.objects.create(
            project=self.project, name='Instalar',
            start_date=date(2026, 11, 2), end_date=date(2026, 11, 6),
        )
        self.other_task = Task.objects.create(
            project=self.other, name='Otra',
            start_date=date(2026, 11, 2), end_date=date(2026, 11, 6),
        )
        self.material = Resource.objects.create(
            project=self.project, kind=Resource.Kind.MATERIAL,
            name='Cables', quantity=Decimal('10'), unit_cost=Decimal('2000'),
        )
        self.professional = Resource.objects.create(
            project=self.project, kind=Resource.Kind.PROFESSIONAL,
            name='Ana', specialty='QA', hours_per_week=Decimal('40'),
            weeks=Decimal('2'), hourly_rate=Decimal('1000'),
        )
        self.other_material = Resource.objects.create(
            project=self.other, kind=Resource.Kind.MATERIAL,
            name='Otros', quantity=Decimal('1'), unit_cost=Decimal('2000'),
        )
        self.url = '/api/resource-assignments/'

    def create(self, **extra):
        data = {
            'task': self.task.id,
            'resource': self.material.id,
            'planned_units': '5.00',
            'actual_units': '3.00',
            **extra,
        }
        return self.client.post(self.url, data, format='json')

    def test_create_snapshots_catalog_price(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data['planned_cost']), Decimal('10000.00'))
        self.assertEqual(Decimal(response.data['actual_cost']), Decimal('6000.00'))
        self.assertEqual(Decimal(response.data['actual_unit_cost']), Decimal('2000.00'))

    def test_update_actual_units_and_unit_cost(self):
        response = self.create()
        pk = response.data['id']
        patched = self.client.patch(f'{self.url}{pk}/', {
            'actual_units': '6.00', 'actual_unit_cost': '2500.00',
        }, format='json')
        self.assertEqual(patched.status_code, 200, patched.data)
        self.assertEqual(Decimal(patched.data['actual_cost']), Decimal('15000.00'))
        self.assertEqual(Decimal(patched.data['planned_cost']), Decimal('10000.00'))

    def test_catalog_price_update_does_not_change_assignment(self):
        response = self.create()
        self.material.unit_cost = Decimal('5000.00')
        self.material.save(update_fields=['unit_cost'])
        assignment = TaskResourceAssignment.objects.get(pk=response.data['id'])
        self.assertEqual(assignment.planned_unit_cost, Decimal('2000.00'))
        self.assertEqual(assignment.planned_cost, Decimal('10000.00'))

    def test_mismatched_projects_are_rejected(self):
        response = self.create(resource=self.other_material.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(TaskResourceAssignment.objects.count(), 0)

    def test_reject_cross_project_patch_and_preserve_original(self):
        created = self.create()
        response = self.client.patch(f'{self.url}{created.data["id"]}/', {
            'task': self.other_task.id,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        original = TaskResourceAssignment.objects.get(pk=created.data['id'])
        self.assertEqual(original.task_id, self.task.id)

    def test_zero_planned_units_rejected(self):
        response = self.create(planned_units='0')
        self.assertEqual(response.status_code, 400)

    def test_negative_actual_units_rejected_with_rollback(self):
        created = self.create()
        response = self.client.patch(f'{self.url}{created.data["id"]}/', {'actual_units': '-5'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(TaskResourceAssignment.objects.get(pk=created.data['id']).actual_units, Decimal('3.00'))

    def test_professional_uses_hourly_rate(self):
        response = self.create(resource=self.professional.id, planned_units='8', actual_units='4')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data['planned_cost']), Decimal('8000.00'))
        self.assertEqual(Decimal(response.data['actual_cost']), Decimal('4000.00'))

    def test_project_summary_and_budget_variance(self):
        self.create()
        response = self.client.get(f'/api/resource-costs/projects/{self.project.id}/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Decimal(response.data['baseline_budget']), Decimal('100000.00'))
        self.assertEqual(Decimal(response.data['planned_resource_cost']), Decimal('10000.00'))
        self.assertEqual(Decimal(response.data['actual_resource_cost']), Decimal('6000.00'))
        self.assertEqual(Decimal(response.data['planned_budget_variance']), Decimal('90000.00'))
        self.assertEqual(response.data['assignment_count'], 1)

    def test_task_summary(self):
        self.create()
        response = self.client.get(f'/api/resource-costs/tasks/{self.task.id}/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Decimal(response.data['actual_minus_planned']), Decimal('-4000.00'))

    def test_filter_by_task_resource_and_project(self):
        self.create()
        other = self.client.post(self.url, {
            'task': self.other_task.id,
            'resource': self.other_material.id,
            'planned_units': '1.00',
        }, format='json')
        self.assertEqual(other.status_code, 201, other.data)
        for filter_key, filter_id in [('project', self.project.id), ('task', self.task.id), ('resource', self.material.id)]:
            results = self.client.get(f'{self.url}?{filter_key}={filter_id}')
            self.assertEqual(results.status_code, 200, results.data)
            self.assertEqual(len(results.data), 1)

    def test_delete_assignment_and_missing_summary(self):
        created = self.create()
        response = self.client.delete(f'{self.url}{created.data["id"]}/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(TaskResourceAssignment.objects.count(), 0)
        missing = self.client.get('/api/resource-costs/projects/999999/')
        self.assertEqual(missing.status_code, 404)

    def test_empty_project_summary_returns_zero_not_null(self):
        response = self.client.get(f'/api/resource-costs/projects/{self.other.id}/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['planned_resource_cost'], '0.00')
        self.assertEqual(response.data['actual_resource_cost'], '0.00')

    def test_assigned_resource_cannot_change_project(self):
        self.create()
        response = self.client.patch(f'/api/resources/{self.material.id}/', {
            'project': self.other.id,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.material.refresh_from_db()
        self.assertEqual(self.material.project_id, self.project.id)

    def test_assigned_resource_cannot_be_deleted(self):
        self.create()
        response = self.client.delete(f'/api/resources/{self.material.id}/')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Resource.objects.filter(pk=self.material.id).exists())

    def test_assigned_resource_cannot_change_kind(self):
        self.create()
        response = self.client.patch(f'/api/resources/{self.material.id}/', {
            'kind': 'OTHER',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.material.refresh_from_db()
        self.assertEqual(self.material.kind, Resource.Kind.MATERIAL)
