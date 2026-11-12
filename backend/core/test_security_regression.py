"""Fase 8.1.5: pruebas HTTP reales con cookies, sesiones y CSRF.

No se utiliza force_authenticate: las peticiones reproducen el flujo del navegador.
"""
import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import Client, TestCase

from core.models import ProjectMembership, UserProfile, UserRole
from projects.models import Project
from projects.resource_models import Resource
from tasks.models import Task
from projects.change_models import ChangeRequest


class SecurityRegressionTests(TestCase):
    PASSWORD = 'SecureTestPass-2026!'

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.admin = user_model.objects.create_superuser(
            username='regression_admin', email='admin@local.test', password=cls.PASSWORD
        )
        cls.member = user_model.objects.create_user(
            username='regression_member', password=cls.PASSWORD
        )
        cls.outsider = user_model.objects.create_user(
            username='regression_outsider', password=cls.PASSWORD
        )
        UserProfile.objects.create(user=cls.member, role=UserRole.PROJECT_USER)
        UserProfile.objects.create(user=cls.outsider, role=UserRole.PROJECT_USER)
        cls.own = Project.objects.create(
            code='REG-815-A', name='Proyecto autorizado', manager_name='QA',
            start_date=date(2026, 11, 2), end_date=date(2026, 12, 31),
            baseline_budget=Decimal('100000.00'),
        )
        cls.foreign = Project.objects.create(
            code='REG-815-B', name='Proyecto restringido', manager_name='QA',
            start_date=date(2026, 11, 2), end_date=date(2026, 12, 31),
            baseline_budget=Decimal('200000.00'),
        )
        ProjectMembership.objects.create(user=cls.member, project=cls.own)
        cls.own_task = Task.objects.create(
            project=cls.own, name='Tarea autorizada',
            start_date=date(2026, 11, 16), end_date=date(2026, 11, 18),
            estimated_duration_days=3,
        )
        cls.foreign_task = Task.objects.create(
            project=cls.foreign, name='Tarea restringida',
            start_date=date(2026, 11, 16), end_date=date(2026, 11, 18),
            estimated_duration_days=3,
        )
        cls.foreign_resource = Resource.objects.create(
            project=cls.foreign, kind='MATERIAL', name='Recurso restringido',
            quantity=Decimal('1.00'), unit='unidad', unit_cost=Decimal('100.00'),
        )
        cls.own_change = ChangeRequest.objects.create(
            project=cls.own, title='Solicitud de prueba', requester='QA',
            requested_at=date(2026, 11, 11), description='Solicitud',
            justification='Validación de permisos', kind='TIME', responsible='QA',
        )

    def new_client(self):
        return Client(enforce_csrf_checks=True)

    def sign_in(self, username):
        client = self.new_client()
        csrf_response = client.get('/api/auth/csrf/')
        self.assertEqual(csrf_response.status_code, 200)
        token = csrf_response.json()['csrfToken']
        response = client.post(
            '/api/auth/login/',
            data=json.dumps({'username': username, 'password': self.PASSWORD}),
            content_type='application/json', HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200, response.content)
        # Django rota el token en login: NO reutilizar el anterior.
        return client, response.json()['csrfToken']

    def json_post(self, client, path, data, token=None):
        headers = {'HTTP_X_CSRFTOKEN': token} if token is not None else {}
        return client.post(path, data=json.dumps(data), content_type='application/json', **headers)

    def test_01_anonymous_cannot_read_protected_data(self):
        client = self.new_client()
        for path in ('/api/projects/', '/api/tasks/', '/api/resources/',
                     '/api/change-requests/', '/api/auth/my-projects/'):
            with self.subTest(path=path):
                self.assertIn(client.get(path).status_code, (401, 403))

    def test_02_bad_credentials_do_not_create_session(self):
        client = self.new_client()
        token = client.get('/api/auth/csrf/').json()['csrfToken']
        response = self.json_post(client, '/api/auth/login/',
                                  {'username': self.member.username, 'password': 'incorrecta'}, token)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(client.get('/api/auth/me/').status_code, 401)

    def test_03_valid_login_survives_subsequent_requests(self):
        client, _ = self.sign_in(self.member.username)
        for _ in range(2):
            self.assertEqual(client.get('/api/auth/me/').json()['user']['username'], self.member.username)
        self.assertEqual(client.get('/api/projects/').status_code, 200)

    def test_04_login_without_csrf_rejected(self):
        client = self.new_client()
        client.get('/api/auth/csrf/')
        response = self.json_post(client, '/api/auth/login/',
                                  {'username': self.member.username, 'password': self.PASSWORD})
        self.assertEqual(response.status_code, 403)

    def test_05_authenticated_post_without_csrf_rejected(self):
        client, _ = self.sign_in(self.member.username)
        response = self.json_post(client, '/api/tasks/',
                                  {'project': self.own.pk, 'name': 'No autorizada'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Task.objects.filter(name='No autorizada').exists())

    def test_06_project_member_list_and_detail_isolation(self):
        client, _ = self.sign_in(self.member.username)
        visible = client.get('/api/projects/')
        self.assertEqual(visible.status_code, 200)
        self.assertEqual({item['id'] for item in visible.json()}, {self.own.pk})
        self.assertEqual(client.get(f'/api/projects/{self.foreign.pk}/').status_code, 404)
        self.assertEqual(client.get(f'/api/tasks/{self.foreign_task.pk}/').status_code, 404)
        self.assertEqual(client.get(f'/api/resources/{self.foreign_resource.pk}/').status_code, 404)

    def test_07_foreign_reference_cannot_create_task(self):
        client, token = self.sign_in(self.member.username)
        response = self.json_post(client, '/api/tasks/', {
            'project': self.foreign.pk, 'name': 'Cruce prohibido',
            'start_date': '2026-11-16', 'end_date': '2026-11-18', 'position': 1,
        }, token)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Task.objects.filter(name='Cruce prohibido').exists())

    def test_08_member_cannot_change_project_or_approve(self):
        client, token = self.sign_in(self.member.username)
        response = client.patch(
            f'/api/projects/{self.own.pk}/',
            data=json.dumps({'name': 'Cambio prohibido'}),
            content_type='application/json', HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 403)
        self.own.refresh_from_db()
        self.assertEqual(self.own.name, 'Proyecto autorizado')
        response = self.json_post(client, f'/api/change-requests/{self.own_change.pk}/approve/',
                                  {'actor': 'admin', 'reason': 'Intento'}, token)
        self.assertEqual(response.status_code, 403)

    def test_09_admin_can_read_both_projects(self):
        client, _ = self.sign_in(self.admin.username)
        self.assertEqual(client.get(f'/api/projects/{self.own.pk}/').status_code, 200)
        self.assertEqual(client.get(f'/api/projects/{self.foreign.pk}/').status_code, 200)
        self.assertEqual(client.get(f'/api/tasks/{self.foreign_task.pk}/').status_code, 200)

    def test_10_user_without_memberships_sees_no_projects(self):
        client, _ = self.sign_in(self.outsider.username)
        result = client.get('/api/auth/my-projects/')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['results'], [])
        self.assertEqual(client.get(f'/api/projects/{self.own.pk}/').status_code, 404)

    def test_11_revoked_membership_blocks_next_request(self):
        client, _ = self.sign_in(self.member.username)
        self.assertEqual(client.get(f'/api/projects/{self.own.pk}/').status_code, 200)
        ProjectMembership.objects.filter(user=self.member, project=self.own).delete()
        self.assertEqual(client.get(f'/api/projects/{self.own.pk}/').status_code, 404)
        self.assertEqual(client.get('/api/auth/my-projects/').json()['results'], [])

    def test_12_logout_invalidates_session(self):
        client, token = self.sign_in(self.member.username)
        response = self.json_post(client, '/api/auth/logout/', {}, token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get('/api/auth/me/').status_code, 401)
        self.assertIn(client.get('/api/tasks/').status_code, (401, 403))

    def test_13_logout_without_csrf_is_rejected_and_session_remains(self):
        client, _ = self.sign_in(self.member.username)
        response = self.json_post(client, '/api/auth/logout/', {})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(client.get('/api/auth/me/').status_code, 200)

    def test_14_server_side_session_deletion_removes_access(self):
        client, _ = self.sign_in(self.member.username)
        session_key = client.cookies['sessionid'].value
        Session.objects.filter(session_key=session_key).delete()
        self.assertEqual(client.get('/api/auth/me/').status_code, 401)
        self.assertIn(client.get('/api/projects/').status_code, (401, 403))

    def test_15_two_sessions_do_not_share_project_access(self):
        member_client, _ = self.sign_in(self.member.username)
        outsider_client, _ = self.sign_in(self.outsider.username)
        self.assertEqual(member_client.get(f'/api/projects/{self.own.pk}/').status_code, 200)
        self.assertEqual(outsider_client.get(f'/api/projects/{self.own.pk}/').status_code, 404)
        self.assertEqual(member_client.get('/api/auth/me/').json()['user']['username'], self.member.username)
        self.assertEqual(outsider_client.get('/api/auth/me/').json()['user']['username'], self.outsider.username)
