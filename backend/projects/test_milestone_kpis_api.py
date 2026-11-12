from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from core.models import ProjectMembership
from projects.models import Milestone, MilestoneKPI, Project


class MilestoneKPIAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username='admin_kpi_822', email='admin@example.test', password='SafePass123!'
        )
        self.member = User.objects.create_user(username='member_kpi_822', password='SafePass123!')
        self.outsider = User.objects.create_user(username='outsider_kpi_822', password='SafePass123!')
        self.project = Project.objects.create(
            code='KPI-822A', name='Proyecto KPI', manager_name='Responsable',
            start_date=date(2026, 11, 1), end_date=date(2026, 12, 31),
        )
        self.foreign_project = Project.objects.create(
            code='KPI-822B', name='Proyecto ajeno', manager_name='Responsable',
            start_date=date(2026, 11, 1), end_date=date(2026, 12, 31),
        )
        ProjectMembership.objects.create(user=self.member, project=self.project)
        self.milestone = Milestone.objects.create(
            project=self.project, name='Entrega validada', due_date=date(2026, 11, 20),
            responsible='Lider', acceptance_criteria='Acta firmada',
        )
        self.foreign_milestone = Milestone.objects.create(
            project=self.foreign_project, name='Hito ajeno', due_date=date(2026, 11, 20),
            responsible='Lider', acceptance_criteria='Acta firmada',
        )
        self.url = reverse('milestone-kpi-list')
        self.payload = {
            'milestone': self.milestone.pk, 'name': 'Entregables aceptados',
            'description': 'Total de entregables', 'responsible': 'Lider QA',
            'kind': 'VALUE', 'direction': 'AT_LEAST', 'unit': 'entregables',
            'target_value': '10.00', 'measured_value': '8.00',
        }

    def create_as_admin(self, payload=None):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.url, payload or self.payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_create_direct_and_not_met(self):
        result = self.create_as_admin()
        self.assertEqual(result['actual_value'], '8.00')
        self.assertEqual(result['achievement_status'], 'NOT_MET')

    def test_met_at_least_when_equal(self):
        result = self.create_as_admin({**self.payload, 'measured_value': '10.00'})
        self.assertEqual(result['achievement_status'], 'MET')

    def test_at_most_direction(self):
        result = self.create_as_admin({
            **self.payload, 'direction': 'AT_MOST', 'target_value': '5.00',
            'measured_value': '4.00',
        })
        self.assertEqual(result['achievement_status'], 'MET')

    def test_without_measurement_is_not_measured(self):
        payload = {**self.payload, 'measured_value': None}
        result = self.create_as_admin(payload)
        self.assertIsNone(result['actual_value'])
        self.assertEqual(result['achievement_status'], 'NOT_MEASURED')

    def test_percentage_is_derived_from_two_values(self):
        result = self.create_as_admin({
            **self.payload, 'kind': 'PERCENTAGE', 'unit': '%',
            'measured_value': None, 'target_value': '75.00',
            'numerator': '9.00', 'denominator': '12.00',
        })
        self.assertEqual(result['actual_value'], '75.00')
        self.assertEqual(result['achievement_status'], 'MET')

    def test_percentage_can_exceed_one_hundred(self):
        result = self.create_as_admin({
            **self.payload, 'kind': 'PERCENTAGE', 'unit': '%',
            'measured_value': None, 'target_value': '100.00',
            'numerator': '15.00', 'denominator': '10.00',
        })
        self.assertEqual(result['actual_value'], '150.00')

    def test_invalid_denominator_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.url, {
            **self.payload, 'kind': 'PERCENTAGE', 'measured_value': None,
            'numerator': '4.00', 'denominator': '0.00',
        }, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(MilestoneKPI.objects.count(), 0)

    def test_partial_percentage_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.url, {
            **self.payload, 'kind': 'PERCENTAGE', 'measured_value': None,
            'numerator': '3.00',
        }, format='json')
        self.assertEqual(response.status_code, 400, response.data)

    def test_negative_value_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.url, {**self.payload, 'measured_value': '-1.00'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_member_can_create_for_own_project(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_member_cannot_create_for_foreign_hito(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.post(self.url, {
            **self.payload, 'milestone': self.foreign_milestone.pk,
        }, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(MilestoneKPI.objects.count(), 0)

    def test_member_cannot_see_foreign_kpi(self):
        foreign = self.create_as_admin({
            **self.payload, 'milestone': self.foreign_milestone.pk,
        })
        self.client.force_authenticate(user=self.member)
        response = self.client.get(reverse('milestone-kpi-detail', args=[foreign['id']]))
        self.assertEqual(response.status_code, 404)
        listed = self.client.get(self.url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.data), 0)

    def test_outsider_list_is_empty(self):
        self.create_as_admin()
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_unauthenticated_request_rejected(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (401, 403))

    def test_cannot_move_kpi_to_another_milestone(self):
        original = self.create_as_admin()
        response = self.client.patch(reverse('milestone-kpi-detail', args=[original['id']]), {
            'milestone': self.foreign_milestone.pk,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MilestoneKPI.objects.get(pk=original['id']).milestone_id, self.milestone.pk)

    def test_patch_measurement_updates_status(self):
        original = self.create_as_admin()
        response = self.client.patch(reverse('milestone-kpi-detail', args=[original['id']]), {
            'measured_value': '12.00',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['achievement_status'], 'MET')

    def test_filter_by_milestone_and_project(self):
        self.create_as_admin()
        by_milestone = self.client.get(self.url, {'milestone': self.milestone.pk})
        by_project = self.client.get(self.url, {'project': self.project.pk})
        self.assertEqual(len(by_milestone.data), 1)
        self.assertEqual(len(by_project.data), 1)
        invalid = self.client.get(self.url, {'milestone': 'foo'})
        self.assertEqual(invalid.status_code, 400)

    def test_delete_authorized(self):
        created = self.create_as_admin()
        response = self.client.delete(reverse('milestone-kpi-detail', args=[created['id']]))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(MilestoneKPI.objects.exists())
