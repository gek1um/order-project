from django.contrib.auth import get_user_model
from datetime import date
from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Project
from .resource_models import Resource


class ResourceAPITests(APITestCase):
    def setUp(self):
        # Fase 8.1.3: el test antiguo comprueba reglas de negocio, no acceso anónimo.
        # Usa ADMIN para conservar sus premisas y probar las reglas originales.
        auth_user = get_user_model().objects.create_superuser(
            username='test_admin_813', email='test813@example.test', password='SafePass123!')
        self.client.force_authenticate(user=auth_user)
        self.project = Project.objects.create(
            code="P-RES-1", name="Proyecto recursos", manager_name="Responsable",
            start_date=date(2026, 11, 1), end_date=date(2027, 1, 31),
            baseline_budget=Decimal("5000000.00"),
        )
        self.other = Project.objects.create(
            code="P-RES-2", name="Proyecto segundo", manager_name="Responsable",
            start_date=date(2026, 11, 1), end_date=date(2027, 1, 31),
        )
        self.url = "/api/resources/"

    def material(self, **kw):
        return {
            "project": self.project.id, "kind": "MATERIAL", "name": "Acero",
            "unit": "kg", "quantity": "12.00", "unit_cost": "1250.50", **kw,
        }

    def test_create_material_and_estimated_cost(self):
        response = self.client.post(self.url, self.material(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Decimal(response.data["estimated_catalog_cost"]), Decimal("15006.00"))

    def test_professional_hours_cost(self):
        response = self.client.post(self.url, {
            "project": self.project.id, "kind": "PROFESSIONAL",
            "name": "Ana", "specialty": "QA", "quantity": "1.00",
            "hours_per_week": "40.00", "weeks": "3.00", "hourly_rate": "15000.00",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data["estimated_catalog_cost"]), Decimal("1800000.00"))

    def test_type_professional_multiplies_headcount(self):
        response = self.client.post(self.url, {
            "project": self.project.id, "kind": "PROFESSIONAL_TYPE",
            "name": "Desarrolladores", "quantity": "2.00",
            "hours_per_week": "20.00", "weeks": "2.00", "hourly_rate": "10000.00",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data["estimated_catalog_cost"]), Decimal("800000.00"))

    def test_licenses_use_quantity_and_periods(self):
        response = self.client.post(self.url, {
            "project": self.project.id, "kind": "LICENSE", "name": "Editor",
            "quantity": "3.00", "unit_cost": "5000.00", "periods": 4,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data["estimated_catalog_cost"]), Decimal("60000.00"))

    def test_missing_required_hourly_rate_is_rejected(self):
        response = self.client.post(self.url, {
            "project": self.project.id, "kind": "PROFESSIONAL",
            "name": "Ana", "specialty": "QA", "hours_per_week": "40.00", "weeks": "2.00",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("hourly_rate", response.data)

    def test_negative_cost_is_rejected(self):
        response = self.client.post(self.url, self.material(unit_cost="-1.00"), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Resource.objects.count(), 0)

    def test_zero_quantity_is_rejected(self):
        response = self.client.post(self.url, self.material(quantity="0"), format="json")
        self.assertEqual(response.status_code, 400)

    def test_invalid_patch_keeps_original(self):
        created = self.client.post(self.url, self.material(), format="json")
        self.assertEqual(created.status_code, 201, created.data)
        response = self.client.patch(f"{self.url}{created.data['id']}/", {"quantity": "-2"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Resource.objects.get(pk=created.data["id"]).quantity, Decimal("12.00"))

    def test_filter_by_project_and_kind(self):
        self.client.post(self.url, self.material(), format="json")
        self.client.post(self.url, self.material(project=self.other.id, name="Otro"), format="json")
        response = self.client.get(f"{self.url}?project={self.project.id}&kind=MATERIAL")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_edit_and_delete(self):
        created = self.client.post(self.url, self.material(), format="json")
        pk = created.data["id"]
        edited = self.client.patch(f"{self.url}{pk}/", {"unit_cost": "1000.00"}, format="json")
        self.assertEqual(edited.status_code, 200, edited.data)
        self.assertEqual(Decimal(edited.data["estimated_catalog_cost"]), Decimal("12000.00"))
        deleted = self.client.delete(f"{self.url}{pk}/")
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(Resource.objects.filter(pk=pk).exists())
