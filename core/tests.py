from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from wallet.models import Wallet


class CoreViewTests(TestCase):
    def test_home_anonymous(self):
        r = self.client.get(reverse("core:home"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "fichas")
        self.assertContains(r, "2,7%")

    def test_signup_creates_user_and_wallet_and_logs_in(self):
        r = self.client.post(
            reverse("core:signup"),
            {"username": "bia", "password1": "senha-forte-123", "password2": "senha-forte-123"},
        )
        self.assertRedirects(r, reverse("core:home"))
        user = get_user_model().objects.get(username="bia")
        self.assertTrue(Wallet.objects.filter(user=user).exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_signup_invalid_rerenders(self):
        r = self.client.post(reverse("core:signup"), {"username": "bia", "password1": "a", "password2": "b"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="bia").exists())

    def test_login_page_renders(self):
        r = self.client.get(reverse("login"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Entrar")

    def test_superuser_without_wallet_gets_one(self):
        user = get_user_model().objects.create_superuser("root", "r@x.com", "x")
        self.client.force_login(user)
        r = self.client.get(reverse("core:home"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Wallet.objects.filter(user=user).exists())
        self.assertContains(r, "1000")


class HealthCheckTests(TestCase):
    @override_settings(ALLOWED_HOSTS=["minhaposta.com.br"], SECURE_SSL_REDIRECT=True)
    def test_probe_from_localhost_bypasses_host_and_https_checks(self):
        r = self.client.get("/healthz", headers={"host": "localhost:8000"})
        self.assertEqual((r.status_code, r.content), (200, b"ok"))
        # sem o atalho, a mesma sonda é redirecionada para HTTPS
        self.assertEqual(self.client.get("/", headers={"host": "minhaposta.com.br"}).status_code, 301)


class RunserverPortTests(TestCase):
    def test_runserver_defaults_to_port_8777(self):
        from django.core.management import get_commands, load_command_class

        self.assertEqual(get_commands()["runserver"], "core")
        self.assertEqual(load_command_class("core", "runserver").default_port, "8777")
