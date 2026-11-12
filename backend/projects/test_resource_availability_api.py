from django.contrib.auth import get_user_model
"""Pruebas funcionales de disponibilidad semanal estimada."""
from datetime import date
from decimal import Decimal

from rest_framework.test import APITestCase

from scheduling.models import WorkCalendar, CalendarException
from tasks.models import Task
from .models import Project
from .resource_models import Resource
from .resource_assignment_models import TaskResourceAssignment


class WeeklyResourceAvailabilityAPITests(APITestCase):
    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code='CAP-01', name='Capacidad', manager_name='Líder',
            start_date=date(2026, 11, 2), end_date=date(2026, 11, 20),
        )
        self.pro = Resource.objects.create(
            project=self.project, kind=Resource.Kind.PROFESSIONAL,
            name='Ana', specialty='Backend', hours_per_week=Decimal('40'),
            weeks=Decimal('3'), hourly_rate=Decimal('1000'),
        )
        self.t1 = Task.objects.create(project=self.project, name='A',
                                      start_date=date(2026, 11, 2), end_date=date(2026, 11, 6))
        self.t2 = Task.objects.create(project=self.project, name='B',
                                      start_date=date(2026, 11, 2), end_date=date(2026, 11, 6))
        self.url = f'/api/resource-availability/projects/{self.project.pk}/'

    def assign(self, task, hours, resource=None):
        return TaskResourceAssignment.objects.create(
            task=task, resource=resource or self.pro,
            planned_units=Decimal(str(hours)), actual_units=Decimal('0'),
            planned_unit_cost=Decimal('1000'), actual_unit_cost=Decimal('1000'),
        )

    def get_week(self, index=0, resource_id=None):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        weeks = [r for r in response.data['weeks'] if r['resource_id'] == (resource_id or self.pro.pk)]
        return weeks[index]

    def test_no_assignments_have_full_capacity(self):
        week = self.get_week()
        self.assertEqual(week['capacity_hours'], '40.00')
        self.assertEqual(week['planned_hours'], '0.00')
        self.assertFalse(week['overallocated'])

    def test_two_tasks_exceed_weekly_capacity(self):
        self.assign(self.t1, 30)
        self.assign(self.t2, 20)
        week = self.get_week()
        self.assertEqual(week['planned_hours'], '50.00')
        self.assertEqual(week['overallocation_hours'], '10.00')
        self.assertTrue(week['overallocated'])

    def test_exact_capacity_not_overallocated(self):
        self.assign(self.t1, 40)
        week = self.get_week()
        self.assertEqual(week['available_hours'], '0.00')
        self.assertFalse(week['overallocated'])

    def test_task_across_two_weeks_is_prorated(self):
        task = Task.objects.create(project=self.project, name='Largo',
                                   start_date=date(2026, 11, 2), end_date=date(2026, 11, 13))
        self.assign(task, 60)
        self.assertEqual(self.get_week(0)['planned_hours'], '30.00')
        self.assertEqual(self.get_week(1)['planned_hours'], '30.00')

    def test_custom_calendar_exception_reduces_capacity(self):
        cal = WorkCalendar.objects.create(project=self.project)
        CalendarException.objects.create(calendar=cal, date=date(2026, 11, 4), is_working=False)
        self.assertEqual(self.get_week()['capacity_hours'], '32.00')

    def test_professional_type_capacity_multiplies_quantity(self):
        pool = Resource.objects.create(project=self.project, kind=Resource.Kind.PROFESSIONAL_TYPE,
                                       name='Equipo QA', quantity=Decimal('2'),
                                       hours_per_week=Decimal('40'), weeks=Decimal('3'),
                                       hourly_rate=Decimal('500'))
        self.assign(self.t1, 70, resource=pool)
        week = self.get_week(resource_id=pool.pk)
        self.assertEqual(week['capacity_hours'], '80.00')
        self.assertFalse(week['overallocated'])

    def test_material_does_not_affect_hours(self):
        material = Resource.objects.create(project=self.project, kind=Resource.Kind.MATERIAL,
                                           name='Cable', quantity=Decimal('5'), unit_cost=Decimal('10'))
        self.assign(self.t1, 100, resource=material)
        self.assertEqual(self.get_week()['planned_hours'], '0.00')
        result = self.client.get(self.url).data
        self.assertEqual(result['resource_count'], 1)

    def test_read_only_does_not_mutate_assignments(self):
        assignment = self.assign(self.t1, 12)
        self.client.get(self.url)
        assignment.refresh_from_db()
        self.assertEqual(assignment.planned_units, Decimal('12'))
        self.assertEqual(assignment.actual_units, Decimal('0'))

    def test_bad_dates_return_400(self):
        for params in ('?from=not-a-date', '?from=2026-11-10&to=2026-11-01',
                       '?from=2026-01-01&to=2028-02-01'):
            response = self.client.get(self.url + params)
            self.assertEqual(response.status_code, 400, response.data)

    def test_unknown_project_returns_404(self):
        response = self.client.get('/api/resource-availability/projects/999999/')
        self.assertEqual(response.status_code, 404)

    def test_zero_working_days_warns_instead_of_dividing_by_zero(self):
        cal = WorkCalendar.objects.create(project=self.project)
        for day in (2, 3, 4, 5, 6):
            CalendarException.objects.create(calendar=cal, date=date(2026, 11, day), is_working=False)
        self.assign(self.t1, 20)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['warnings'][0]['code'], 'TASK_NO_WORKING_DAYS')
        self.assertEqual(self.get_week()['planned_hours'], '0.00')
