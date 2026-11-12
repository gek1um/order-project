"""Pruebas de sesión con verificación real del encabezado CSRF."""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class SessionAuthApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="analista", password="UnaClaveSegura-123", email="analista@example.test"
        )
        cls.inactive = get_user_model().objects.create_user(
            username="inactivo", password="UnaClaveSegura-123", is_active=False
        )

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def _csrf(self):
        response = self.client.get(reverse("auth-csrf"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)
        return response.json()["csrfToken"]

    def _login(self, username="analista", password="UnaClaveSegura-123"):
        return self.client.post(
            reverse("auth-login"),
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self._csrf(),
        )

    def test_csrf_endpoint_sends_cookie_and_token(self):
        self.assertTrue(self._csrf())

    def test_anonymous_me_is_unauthorized(self):
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 401)

    def test_login_requires_csrf(self):
        response = self.client.post(
            reverse("auth-login"),
            data=json.dumps({"username": "analista", "password": "UnaClaveSegura-123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_login_and_me(self):
        response = self._login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["username"], "analista")
        self.assertNotIn("password", response.json()["user"])
        self.assertTrue(response.json()["csrfToken"])
        me = self.client.get(reverse("auth-me"))
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["id"], self.user.pk)

    def test_incorrect_password(self):
        self.assertEqual(self._login(password="incorrecta").status_code, 401)

    def test_inactive_user_cannot_log_in(self):
        self.assertEqual(self._login(username="inactivo").status_code, 401)

    def test_missing_fields(self):
        token = self._csrf()
        response = self.client.post(
            reverse("auth-login"), data=json.dumps({"username": "analista"}),
            content_type="application/json", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_json(self):
        response = self.client.post(
            reverse("auth-login"), data="{invalid", content_type="application/json",
            HTTP_X_CSRFTOKEN=self._csrf(),
        )
        self.assertEqual(response.status_code, 400)

    def test_non_json_body(self):
        response = self.client.post(
            reverse("auth-login"), data="username=analista", content_type="text/plain",
            HTTP_X_CSRFTOKEN=self._csrf(),
        )
        self.assertEqual(response.status_code, 415)

    def test_logout_requires_csrf(self):
        self.assertEqual(self._login().status_code, 200)
        self.assertEqual(self.client.post(reverse("auth-logout")).status_code, 403)
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 200)

    def test_logout_closes_session(self):
        response = self._login()
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("auth-logout"), HTTP_X_CSRFTOKEN=response.json()["csrfToken"]
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 401)

    def test_logout_anonymous_is_unauthorized(self):
        response = self.client.post(reverse("auth-logout"), HTTP_X_CSRFTOKEN=self._csrf())
        self.assertEqual(response.status_code, 401)

    def test_http_methods_are_restricted(self):
        self.assertEqual(self.client.get(reverse("auth-login")).status_code, 405)
        self.assertEqual(self.client.get(reverse("auth-logout")).status_code, 405)
        self.assertEqual(
            self.client.post(
                reverse("auth-me"),
                HTTP_X_CSRFTOKEN=self._csrf(),
            ).status_code,
            405,
        )
