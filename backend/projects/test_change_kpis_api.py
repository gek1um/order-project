from django.contrib.auth import get_user_model
"""Regresión Fase 6.3: indicadores derivados de datos persistidos."""
from datetime import date, datetime
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from .change_models import ChangeRequest
from .models import Project


class ProjectChangeKpiAPITests(APITestCase):
    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code='KPI63-A', name='Proyecto KPI', manager_name='PM',
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
            baseline_budget=Decimal('100000.00'),
        )
        self.other = Project.objects.create(
            code='KPI63-B', name='Proyecto separado', manager_name='PM',
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        self.url = f'/api/change-kpis/projects/{self.project.pk}/'

    def change(self, status=ChangeRequest.Status.OPEN, project=None,
               requested_at=date(2026, 1, 10), decided_at=None,
               committed_date=None, actual_completion_date=None):
        return ChangeRequest.objects.create(
            project=project or self.project, title='Solicitud', requester='Equipo',
            requested_at=requested_at, description='Motivo de cambio',
            justification='Necesidad', kind=ChangeRequest.Kind.TIME,
            status=status, responsible='Jefatura', decided_at=decided_at,
            committed_date=committed_date,
            actual_completion_date=actual_completion_date,
        )

    @staticmethod
    def timestamp(year, month, day):
        return timezone.make_aware(datetime(year, month, day, 12, 0))

    def test_empty_project_has_null_metrics(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['counts']['total'], 0)
        self.assertIsNone(r.data['kpis']['approval_rate']['value'])
        self.assertIsNone(r.data['kpis']['average_decision_days']['value'])
        self.assertIsNone(r.data['kpis']['on_time_closure_rate']['value'])

    def test_open_under_review_not_decided(self):
        self.change('OPEN')
        self.change('UNDER_REVIEW')
        r = self.client.get(self.url)
        self.assertEqual(r.data['counts']['total'], 2)
        self.assertEqual(r.data['counts']['decided'], 0)
        self.assertIsNone(r.data['kpis']['approval_rate']['value'])

    def test_approval_rate_includes_approved_implementing_and_closed(self):
        for status in ('APPROVED', 'IMPLEMENTING', 'CLOSED', 'REJECTED'):
            self.change(status=status)
        r = self.client.get(self.url)
        self.assertEqual(r.data['kpis']['approval_rate']['value'], 75.00)
        self.assertEqual(r.data['kpis']['approval_rate']['denominator'], 4)
        self.assertEqual(r.data['kpis']['approval_rate']['numerator'], 3)

    def test_all_rejected_gives_zero_not_null(self):
        self.change('REJECTED')
        r = self.client.get(self.url)
        self.assertEqual(r.data['kpis']['approval_rate']['value'], 0)

    def test_average_decision_days_uses_request_date(self):
        self.change('APPROVED', decided_at=self.timestamp(2026, 1, 12))
        self.change('REJECTED', decided_at=self.timestamp(2026, 1, 14))
        r = self.client.get(self.url)
        self.assertEqual(r.data['kpis']['average_decision_days']['value'], 3.0)
        self.assertEqual(r.data['kpis']['average_decision_days']['observations'], 2)

    def test_missing_decided_date_excluded_and_reported(self):
        self.change('APPROVED', decided_at=self.timestamp(2026, 1, 12))
        self.change('REJECTED', decided_at=None)
        r = self.client.get(self.url)
        kpi = r.data['kpis']['average_decision_days']
        self.assertEqual(kpi['value'], 2.0)
        self.assertEqual(kpi['excluded_missing_or_invalid_date'], 1)

    def test_invalid_decision_date_excluded(self):
        self.change('REJECTED', decided_at=self.timestamp(2026, 1, 9))
        r = self.client.get(self.url)
        self.assertIsNone(r.data['kpis']['average_decision_days']['value'])
        self.assertEqual(r.data['kpis']['average_decision_days']['excluded_missing_or_invalid_date'], 1)

    def test_on_time_rate_counts_closed_with_both_dates(self):
        self.change('CLOSED', committed_date=date(2026, 1, 20),
                    actual_completion_date=date(2026, 1, 20))
        self.change('CLOSED', committed_date=date(2026, 1, 20),
                    actual_completion_date=date(2026, 1, 18))
        self.change('CLOSED', committed_date=date(2026, 1, 20),
                    actual_completion_date=date(2026, 1, 22))
        self.change('CLOSED', committed_date=None,
                    actual_completion_date=date(2026, 1, 19))
        r = self.client.get(self.url)
        kpi = r.data['kpis']['on_time_closure_rate']
        self.assertEqual(kpi['value'], 66.67)
        self.assertEqual(kpi['denominator'], 3)
        self.assertEqual(kpi['excluded_without_dates'], 1)

    def test_closed_without_commitment_is_not_false_failure(self):
        self.change('CLOSED', committed_date=None,
                    actual_completion_date=date(2026, 1, 19))
        r = self.client.get(self.url)
        self.assertIsNone(r.data['kpis']['on_time_closure_rate']['value'])
        self.assertEqual(r.data['counts']['closed'], 1)

    def test_other_project_is_excluded(self):
        self.change('REJECTED', project=self.other)
        self.change('APPROVED', decided_at=self.timestamp(2026, 1, 12))
        r = self.client.get(self.url)
        self.assertEqual(r.data['counts']['total'], 1)
        self.assertEqual(r.data['kpis']['approval_rate']['value'], 100)

    def test_requested_at_filter_is_inclusive(self):
        self.change('APPROVED', requested_at=date(2026, 1, 1))
        self.change('REJECTED', requested_at=date(2026, 1, 15))
        self.change('REJECTED', requested_at=date(2026, 2, 1))
        r = self.client.get(self.url + '?from=2026-01-01&to=2026-01-15')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['counts']['total'], 2)
        self.assertEqual(r.data['kpis']['approval_rate']['value'], 50.00)
        self.assertEqual(r.data['period']['requested_to'], '2026-01-15')

    def test_one_sided_date_filter(self):
        self.change('APPROVED', requested_at=date(2026, 1, 1))
        self.change('REJECTED', requested_at=date(2026, 2, 1))
        r = self.client.get(self.url + '?from=2026-02-01')
        self.assertEqual(r.data['counts']['total'], 1)
        self.assertEqual(r.data['counts']['rejected'], 1)

    def test_invalid_date_filter_returns_400(self):
        r = self.client.get(self.url + '?from=no-es-fecha')
        self.assertEqual(r.status_code, 400)

    def test_inverted_period_returns_400(self):
        r = self.client.get(self.url + '?from=2026-03-01&to=2026-01-01')
        self.assertEqual(r.status_code, 400)

    def test_unknown_project_returns_404(self):
        r = self.client.get('/api/change-kpis/projects/999999/')
        self.assertEqual(r.status_code, 404)

    def test_post_is_not_supported(self):
        r = self.client.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 405)

    def test_read_only_endpoint_does_not_modify_changes(self):
        change = self.change('APPROVED', decided_at=self.timestamp(2026, 1, 12))
        old = change.updated_at
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        change.refresh_from_db()
        self.assertEqual(change.updated_at, old)
