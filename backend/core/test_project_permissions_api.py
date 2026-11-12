"""Seguridad multi-proyecto y decisiones autenticadas (fase 8.1.3)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework.test import APITestCase

from core.models import ProjectMembership, UserProfile, UserRole
from projects.models import Project
from projects.milestone_models import Milestone
from projects.resource_models import Resource
from projects.change_models import ChangeRequest
from tasks.models import Task
from scheduling.models import WorkCalendar, CalendarException, TaskDependency


class ProjectPermissionAPITests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser('segadmin', 'admin@example.test', 'SafePass123!')
        self.member = user_model.objects.create_user('member', password='SafePass123!')
        self.stranger = user_model.objects.create_user('stranger', password='SafePass123!')
        UserProfile.objects.create(user=self.member, role=UserRole.PROJECT_USER)
        UserProfile.objects.create(user=self.stranger, role=UserRole.PROJECT_USER)
        self.project = Project.objects.create(code='SEC-1', name='Asignado', manager_name='QA',
            start_date=date(2026,11,2), end_date=date(2026,12,31), baseline_budget=Decimal('300000'))
        self.other = Project.objects.create(code='SEC-2', name='Reservado', manager_name='QA',
            start_date=date(2026,11,2), end_date=date(2026,12,31), baseline_budget=Decimal('500000'))
        ProjectMembership.objects.create(user=self.member, project=self.project)
        self.task = Task.objects.create(project=self.project, name='Tarea asignada',
            start_date=date(2026,11,16), end_date=date(2026,11,18), estimated_duration_days=3)
        self.other_task = Task.objects.create(project=self.other, name='Tarea reservada',
            start_date=date(2026,11,16), end_date=date(2026,11,18), estimated_duration_days=3)
        self.resource = Resource.objects.create(project=self.project, kind='MATERIAL', name='Cable',
            quantity=Decimal('2'), unit='m', unit_cost=Decimal('100'))
        self.other_resource = Resource.objects.create(project=self.other, kind='MATERIAL', name='Secreto',
            quantity=Decimal('2'), unit='m', unit_cost=Decimal('100'))
        self.milestone = Milestone.objects.create(project=self.project, name='Aprobación',
            due_date=date(2026,11,20), responsible='QA', acceptance_criteria='Conforme')
        self.foreign_milestone = Milestone.objects.create(project=self.other, name='Reservado',
            due_date=date(2026,11,20), responsible='QA', acceptance_criteria='Conforme')
        self.calendar = WorkCalendar.objects.create(project=self.project)
        self.other_calendar = WorkCalendar.objects.create(project=self.other)
        self.exception = CalendarException.objects.create(calendar=self.other_calendar,
            date=date(2026,11,21), is_working=False)
        self.change = ChangeRequest.objects.create(project=self.project, title='Cambio propio',
            requester='Cliente', requested_at=date(2026,11,11), description='Ajustar',
            justification='Motivo', kind='TIME', responsible='QA')
        self.foreign_change = ChangeRequest.objects.create(project=self.other, title='Cambio secreto',
            requester='Cliente', requested_at=date(2026,11,11), description='Reservado',
            justification='Motivo', kind='TIME', responsible='QA')
        self.client.force_authenticate(user=self.member)

    def test_anonymous_is_denied(self):
        self.client.force_authenticate(user=None)
        for uri in ['/api/projects/', '/api/tasks/', '/api/resources/', '/api/change-requests/',
                    '/api/scheduling/projects/%s/schedule/' % self.project.pk]:
            self.assertIn(self.client.get(uri).status_code, [401,403], uri)

    def test_member_only_sees_assigned_project(self):
        response=self.client.get('/api/projects/')
        self.assertEqual(response.status_code,200)
        self.assertEqual([item['id'] for item in response.data],[self.project.pk])
        self.assertEqual(self.client.get(f'/api/projects/{self.other.pk}/').status_code,404)

    def test_unassigned_member_sees_none(self):
        self.client.force_authenticate(user=self.stranger)
        self.assertEqual(len(self.client.get('/api/projects/').data),0)
        self.assertEqual(self.client.get(f'/api/projects/{self.project.pk}/').status_code,404)

    def test_tasks_filtered_and_foreign_detail_masked(self):
        self.assertEqual([x['id'] for x in self.client.get('/api/tasks/').data],[self.task.pk])
        self.assertEqual(self.client.get(f'/api/tasks/{self.other_task.pk}/').status_code,404)
        self.assertEqual(self.client.patch(f'/api/tasks/{self.other_task.pk}/',{'name':'Intrusión'},format='json').status_code,404)

    def test_foreign_task_create_is_rejected(self):
        response=self.client.post('/api/tasks/',{'project':self.other.pk,'name':'Intrusión',
            'start_date':'2026-11-16','end_date':'2026-11-17','position':1},format='json')
        self.assertEqual(response.status_code,400)
        self.assertFalse(Task.objects.filter(name='Intrusión').exists())

    def test_project_modifications_require_admin(self):
        self.assertEqual(self.client.patch(f'/api/projects/{self.project.pk}/',{'name':'Otro'},format='json').status_code,403)
        self.assertEqual(self.client.post('/api/projects/',{'name':'Nuevo'},format='json').status_code,403)
        self.assertEqual(self.client.delete(f'/api/projects/{self.project.pk}/').status_code,403)

    def test_resources_and_milestones_are_scoped(self):
        self.assertEqual([x['id'] for x in self.client.get('/api/resources/').data],[self.resource.pk])
        self.assertEqual(self.client.get(f'/api/resources/{self.other_resource.pk}/').status_code,404)
        self.assertEqual(self.client.get(f'/api/milestones/{self.foreign_milestone.pk}/').status_code,404)
        response=self.client.post('/api/resources/',{'project':self.other.pk,'kind':'MATERIAL',
            'name':'Infiltrado','quantity':'1','unit':'u','unit_cost':'1'},format='json')
        self.assertEqual(response.status_code,400)

    def test_calendar_and_exceptions_are_scoped(self):
        self.assertEqual(self.client.get(f'/api/scheduling/calendars/{self.other_calendar.pk}/').status_code,404)
        self.assertEqual(self.client.get(f'/api/scheduling/exceptions/{self.exception.pk}/').status_code,404)
        response=self.client.post('/api/scheduling/exceptions/',{
            'calendar':self.other_calendar.pk,'date':'2026-11-25','is_working':False},format='json')
        self.assertEqual(response.status_code,400)

    def test_dependent_task_references_do_not_cross_project(self):
        response=self.client.post('/api/scheduling/dependencies/',{
            'predecessor':self.task.pk,'successor':self.other_task.pk,
            'dependency_type':'FS','lag_days':0},format='json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(TaskDependency.objects.count(),0)

    def test_resource_assignments_do_not_cross_project(self):
        response=self.client.post('/api/resource-assignments/',{
            'task':self.task.pk,'resource':self.other_resource.pk,
            'planned_units':'2','actual_units':'0'},format='json')
        self.assertEqual(response.status_code,400)

    def test_project_calculations_and_schedule_are_private(self):
        for suffix in ['calendar/','schedule/']:
            self.assertEqual(self.client.get(f'/api/scheduling/projects/{self.other.pk}/{suffix}').status_code,404)
        self.assertEqual(self.client.post(f'/api/scheduling/projects/{self.other.pk}/calculate/',{
            'operation':'is_working_day','start_date':'2026-11-16'},format='json').status_code,404)
        self.assertEqual(self.client.post(f'/api/scheduling/tasks/{self.other_task.pk}/preview/',{
            'start_date':'2026-11-17','duration_days':3},format='json').status_code,404)

    def test_cost_and_kpi_endpoints_do_not_expose_foreign_data(self):
        routes=[f'/api/resource-costs/projects/{self.other.pk}/',
            f'/api/resource-costs/tasks/{self.other_task.pk}/',
            f'/api/resource-availability/projects/{self.other.pk}/',
            f'/api/change-kpis/projects/{self.other.pk}/']
        for route in routes:self.assertEqual(self.client.get(route).status_code,404,route)

    def test_change_requests_list_and_detail_are_scoped(self):
        data=self.client.get('/api/change-requests/').data
        self.assertEqual([item['id'] for item in data],[self.change.pk])
        self.assertEqual(self.client.get(f'/api/change-requests/{self.foreign_change.pk}/').status_code,404)
        self.assertEqual(self.client.post('/api/change-requests/',{
            'project':self.other.pk,'title':'Filtrado','requester':'X','description':'X',
            'justification':'X','kind':'TIME'},format='json').status_code,400)

    def test_member_cannot_approve_or_reject(self):
        for action in ['approve','reject']:
            response=self.client.post(f'/api/change-requests/{self.change.pk}/{action}/',
                {'actor':'Admin falso','reason':'X'},format='json')
            self.assertEqual(response.status_code,403)

    def test_admin_can_access_other_project(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get(f'/api/projects/{self.other.pk}/').status_code,200)
        self.assertEqual(self.client.get(f'/api/tasks/{self.other_task.pk}/').status_code,200)
        self.assertEqual(self.client.get(f'/api/resource-costs/projects/{self.other.pk}/').status_code,200)

    def test_actor_is_bound_to_authenticated_session(self):
        response=self.client.post(f'/api/change-requests/{self.change.pk}/submit/',
            {'actor':'Administrador falso'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['events'][-1]['actor'],self.member.username)
        self.client.force_authenticate(user=self.admin)
        response=self.client.post(f'/api/change-requests/{self.change.pk}/approve/',
            {'actor':'Otro', 'reason':'Revisado'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['decided_by'],self.admin.username)

    def test_unauthorized_post_without_csrf_is_rejected_for_real_session(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.member)
        response=client.post('/api/tasks/',data='{}',content_type='application/json')
        self.assertEqual(response.status_code,403)
