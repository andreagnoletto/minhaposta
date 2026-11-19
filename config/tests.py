import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ProductionSettingsTests(SimpleTestCase):
    def run_settings_import(self, environment):
        return subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def test_production_requires_secret_key(self):
        environment = os.environ.copy()
        environment["DJANGO_DEBUG"] = "False"
        environment.pop("DJANGO_SECRET_KEY", None)

        result = self.run_settings_import(environment)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Defina DJANGO_SECRET_KEY", result.stderr)

    def test_production_security_defaults_and_environment(self):
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_DEBUG": "False",
                "DJANGO_SECRET_KEY": "temporary-test-key-not-used-outside-tests",
                "DJANGO_ALLOWED_HOSTS": "example.com, www.example.com",
                "DJANGO_SECURE_HSTS_SECONDS": "31536000",
            }
        )
        environment.pop("DJANGO_SECURE_SSL_REDIRECT", None)

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import config.settings as s; "
                    "assert s.DEBUG is False; "
                    "assert s.ALLOWED_HOSTS == ['example.com', 'www.example.com']; "
                    "assert s.SECURE_SSL_REDIRECT is True; "
                    "assert s.SESSION_COOKIE_SECURE is True; "
                    "assert s.CSRF_COOKIE_SECURE is True; "
                    "assert s.SECURE_HSTS_SECONDS == 31536000; "
                    "assert s.SECURE_HSTS_INCLUDE_SUBDOMAINS is True; "
                    "assert s.SECURE_HSTS_PRELOAD is True"
                ),
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
