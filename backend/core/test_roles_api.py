"""Pruebas de roles/membresías con sesiones y CSRF real."""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import ProjectMembership, UserProfile, UserRole
from projects.models import Project


class RolesAndMembershipsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.admin = U.objects.create_superuser(username="adminroles", email="admin@example.test", password="ClaveAdminSegura-123")
        cls.admin_normal = U.objects.create_user(username="adminasignado", password="ClaveAdminSegura-123")
        UserProfile.objects.create(user=cls.admin_normal, role=UserRole.ADMIN)
        cls.user1 = U.objects.create_user(username="proyecto1", password="ClaveUsuarioSegura-123")
        cls.user2 = U.objects.create_user(username="proyecto2", password="ClaveUsuarioSegura-123")
        cls.project1 = Project.objects.create(code="PR-SEG-01", name="Proyecto 1", manager_name="Gestor", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        cls.project2 = Project.objects.create(code="PR-SEG-02", name="Proyecto 2", manager_name="Gestor", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def auth(self, user):
        self.client.force_login(user)
        return self.client.get(reverse("auth-csrf")).json()["csrfToken"]

    def send(self, method, url, payload, token=None):
        kwargs = {"data": json.dumps(payload), "content_type": "application/json"}
        if token is not None:
            kwargs["HTTP_X_CSRFTOKEN"] = token
        return getattr(self.client, method)(url, **kwargs)

    def test_anonymous_cannot_list_users(self):
        self.assertEqual(self.client.get(reverse("auth-users")).status_code, 401)

    def test_project_user_cannot_list_users(self):
        self.auth(self.user1)
        self.assertEqual(self.client.get(reverse("auth-users")).status_code, 403)

    def test_admin_lists_users(self):
        self.auth(self.admin)
        r = self.client.get(reverse("auth-users"))
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.json()["results"]), 4)
        self.assertTrue(all("password" not in x for x in r.json()["results"]))

    def test_non_superuser_admin_can_manage(self):
        token = self.auth(self.admin_normal)
        r = self.send("patch", reverse("auth-user-role", args=[self.user1.pk]), {"role": "ADMIN"}, token)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user"]["role"], "ADMIN")

    def test_admin_creates_user_with_role_and_hashed_password(self):
        token = self.auth(self.admin)
        r = self.send("post", reverse("auth-users"), {"username": "newdev", "password": "UnaClaveNueva-123!", "role": "PROJECT_USER"}, token)
        self.assertEqual(r.status_code, 201)
        u = get_user_model().objects.get(username="newdev")
        self.assertTrue(u.check_password("UnaClaveNueva-123!"))
        self.assertEqual(UserProfile.objects.get(user=u).role, UserRole.PROJECT_USER)

    def test_bad_role_is_rejected(self):
        token = self.auth(self.admin)
        r = self.send("patch", reverse("auth-user-role", args=[self.user1.pk]), {"role": "ROOT"}, token)
        self.assertEqual(r.status_code, 400)

    def test_csrf_required_to_assign_roles(self):
        self.auth(self.admin)
        r = self.send("patch", reverse("auth-user-role", args=[self.user1.pk]), {"role": "ADMIN"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get(reverse("auth-me")).json()["user"]["role"], "ADMIN")
        self.assertEqual(UserProfile.objects.filter(user=self.user1).count(), 0)

    def test_cannot_change_superuser_role(self):
        token = self.auth(self.admin)
        r = self.send("patch", reverse("auth-user-role", args=[self.admin.pk]), {"role": "PROJECT_USER"}, token)
        self.assertEqual(r.status_code, 403)

    def test_self_demotion_disallowed(self):
        token = self.auth(self.admin_normal)
        r = self.send("patch", reverse("auth-user-role", args=[self.admin_normal.pk]), {"role": "PROJECT_USER"}, token)
        self.assertEqual(r.status_code, 403)

    def test_create_membership_and_filter(self):
        token = self.auth(self.admin)
        url = reverse("auth-project-memberships")
        r = self.send("post", url, {"user": self.user1.pk, "project": self.project1.pk}, token)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(ProjectMembership.objects.count(), 1)
        filtered = self.client.get(url, {"project": self.project1.pk})
        self.assertEqual(len(filtered.json()["results"]), 1)

    def test_duplicate_membership_is_idempotent(self):
        token = self.auth(self.admin)
        url = reverse("auth-project-memberships")
        obj = {"user": self.user1.pk, "project": self.project1.pk}
        self.assertEqual(self.send("post", url, obj, token).status_code, 201)
        self.assertEqual(self.send("post", url, obj, token).status_code, 200)
        self.assertEqual(ProjectMembership.objects.count(), 1)

    def test_cannot_assign_others_without_admin(self):
        token = self.auth(self.user1)
        r = self.send("post", reverse("auth-project-memberships"), {"user": self.user1.pk, "project": self.project1.pk}, token)
        self.assertEqual(r.status_code, 403)

    def test_membership_csrf_required(self):
        self.auth(self.admin)
        r = self.send("post", reverse("auth-project-memberships"), {"user": self.user1.pk, "project": self.project1.pk})
        self.assertEqual(r.status_code, 403)

    def test_my_projects_limits_regular_user(self):
        ProjectMembership.objects.create(user=self.user1, project=self.project1)
        self.auth(self.user1)
        r = self.client.get(reverse("auth-my-projects"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([x["id"] for x in r.json()["results"]], [self.project1.pk])

    def test_my_projects_admin_sees_all(self):
        self.auth(self.admin)
        r = self.client.get(reverse("auth-my-projects"))
        self.assertEqual(len(r.json()["results"]), 2)

    def test_delete_membership(self):
        m = ProjectMembership.objects.create(user=self.user1, project=self.project1)
        token = self.auth(self.admin)
        r = self.client.delete(reverse("auth-project-membership-detail", args=[m.pk]), HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 204)
        self.assertFalse(ProjectMembership.objects.filter(pk=m.pk).exists())

    def test_login_identity_includes_role(self):
        self.auth(self.admin_normal)
        self.assertEqual(self.client.get(reverse("auth-me")).json()["user"]["role"], "ADMIN")
        self.auth(self.user1)
        self.assertEqual(self.client.get(reverse("auth-me")).json()["user"]["role"], "PROJECT_USER")
