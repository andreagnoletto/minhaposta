"""Base para testes de ponta a ponta com Playwright.

Os testes rodam com ``manage.py test e2e`` e usam o ``StaticLiveServerTestCase``
do Django, então não precisam de servidor nem de banco externos. Exigem
``requirements-dev.txt`` e ``python -m playwright install chromium``; sem isso,
a suíte inteira é pulada em vez de falhar.
"""

import os
import unittest

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - só acontece sem requirements-dev
    sync_playwright = None
    PlaywrightError = Exception

MOBILE = {"width": 375, "height": 740}
DESKTOP = {"width": 1280, "height": 800}


@unittest.skipUnless(sync_playwright, "Playwright não instalado (pip install -r requirements-dev.txt)")
class PlaywrightTestCase(StaticLiveServerTestCase):
    viewport = DESKTOP
    reduced_motion = "reduce"

    @classmethod
    def setUpClass(cls):
        # O Playwright síncrono roda um event loop; o Django precisa ser avisado
        # para permitir o acesso ao banco a partir dos testes.
        os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch()
        except PlaywrightError as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f"Chromium indisponível: execute `python -m playwright install chromium` ({exc})")
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        super().setUp()
        self.context = self.browser.new_context(
            viewport=self.viewport, reduced_motion=self.reduced_motion, locale="pt-BR"
        )
        self.page = self.context.new_page()
        self.console_errors = []
        self.page.on("pageerror", lambda exc: self.console_errors.append(str(exc)))

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.console_errors, [], "erros de JavaScript na página")
        super().tearDown()

    def url(self, path: str) -> str:
        return f"{self.live_server_url}{path}"

    def goto(self, path: str):
        self.page.goto(self.url(path))
        self.page.wait_for_load_state("networkidle")

    def create_user(self, username="ana", password="Fichas-Treino-2026"):
        return get_user_model().objects.create_user(username, password=password)

    def login(self, user):
        """Autentica no navegador reaproveitando a sessão do ``Client`` do Django."""
        client = Client()
        client.force_login(user)
        cookie = client.cookies["sessionid"]
        self.context.add_cookies(
            [{"name": "sessionid", "value": cookie.value, "url": self.live_server_url}]
        )

    def has_horizontal_overflow(self) -> bool:
        return self.page.evaluate(
            "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )

    def is_in_viewport(self, selector: str) -> bool:
        return self.page.evaluate(
            """(selector) => {
                const el = document.querySelector(selector);
                if (!el) return false;
                const r = el.getBoundingClientRect();
                return r.bottom > 0 && r.top < window.innerHeight;
            }""",
            selector,
        )

    def accessible_text(self, selector: str) -> str:
        """Texto como um leitor de tela o recebe: ignora o que está em ``aria-hidden``."""
        return self.page.evaluate(
            """(selector) => {
                const clone = document.querySelector(selector).cloneNode(true);
                clone.querySelectorAll('[aria-hidden="true"], script, style').forEach(el => el.remove());
                return clone.textContent.replace(/\\s+/g, ' ').trim();
            }""",
            selector,
        )
