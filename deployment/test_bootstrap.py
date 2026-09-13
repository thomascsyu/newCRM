"""Startup helpers used by the Zeabur/Docker entrypoint. No database required."""
import unittest
from contextlib import chdir
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from crm.security.workspace import WorkspaceIdentityError
from deployment.bootstrap import (
    common_site_config,
    google_credentials_configured,
    installed_apps,
    required,
    runtime_settings,
)
from deployment.startup_probe import HEALTH_PATH, probe_status


class BootstrapSettingsTests(unittest.TestCase):
    def valid_env(self, **updates):
        env = {
            "COMPANY_EMAIL_DOMAIN": "gabriel.hk",
            "COMPANY_ADMIN_EMAIL": "thomas@gabriel.hk",
            "CRM_PUBLIC_URL": "https://isocrm.pro",
            "DB_HOST": "mariadb",
            "DB_PORT": "3306",
            "REDIS_URL": "redis://:secret@redis:6379/0",
        }
        env.update(updates)
        return env

    def test_missing_required_variable(self):
        with self.assertRaisesRegex(RuntimeError, "DB_HOST"):
            required("DB_HOST", {})

    def test_empty_google_credentials_do_not_block_startup(self):
        env = self.valid_env(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="")
        settings = runtime_settings(env)
        self.assertFalse(settings["google_ready"])
        self.assertFalse(google_credentials_configured(env))
        self.assertEqual(settings["origin"], "https://isocrm.pro")
        self.assertEqual(common_site_config(settings)["host_name"], "https://isocrm.pro")

    def test_google_credentials_are_detected_when_set(self):
        env = self.valid_env(GOOGLE_CLIENT_ID="client", GOOGLE_CLIENT_SECRET="secret")
        self.assertTrue(runtime_settings(env)["google_ready"])

    def test_invalid_public_url_still_fails_closed(self):
        with self.assertRaises(WorkspaceIdentityError):
            runtime_settings(self.valid_env(CRM_PUBLIC_URL="http://isocrm.pro"))

    def test_admin_must_match_company_domain(self):
        with self.assertRaises(WorkspaceIdentityError):
            runtime_settings(self.valid_env(COMPANY_ADMIN_EMAIL="other@example.com"))


class StartupProbeTests(unittest.TestCase):
    def test_health_path_is_ready_for_zeabur(self):
        self.assertEqual(HEALTH_PATH, "/api/method/crm.company_auth.health")
        code, body = probe_status(HEALTH_PATH)
        self.assertEqual(code, 200)
        self.assertEqual(body, {"status": "starting"})

    def test_health_path_ignores_trailing_slash_and_query(self):
        code, body = probe_status(HEALTH_PATH + "/?probe=1")
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "starting")

    def test_other_paths_stay_unavailable(self):
        self.assertEqual(probe_status("/crm")[0], 503)


class DependencyWaitTests(unittest.TestCase):
    def test_wait_raises_after_exhausted_retries(self):
        import sys
        from types import SimpleNamespace
        from deployment.bootstrap import wait_for_dependencies

        class RedisError(Exception):
            pass

        class Redis:
            @staticmethod
            def from_url(url):
                raise RedisError("down")

        fake_redis = SimpleNamespace(Redis=Redis, RedisError=RedisError)
        missing = Path("/tmp/missing-site-config.json")
        settings = {"db_host": "127.0.0.1", "db_port": 1, "redis_url": "redis://127.0.0.1:1/0"}
        with (
            patch.dict(sys.modules, {"redis": fake_redis}),
            patch("deployment.bootstrap.time.sleep", return_value=None),
            self.assertRaisesRegex(RuntimeError, "MariaDB or Redis"),
        ):
            wait_for_dependencies(settings, missing, attempts=2, delay=0, environ={"DB_ROOT_PASSWORD": "x"})


class InstalledAppsTests(unittest.TestCase):
    def test_framework_logs_resolve_inside_bench_and_site(self):
        with TemporaryDirectory() as tmp:
            bench = Path(tmp).resolve() / "frappe-bench"
            sites = bench / "sites"
            site_logs = sites / "crm.internal" / "logs"
            site_logs.mkdir(parents=True)
            (bench / "logs").mkdir()

            def connect():
                # Frappe's logger opens both paths relative to its working directory.
                for path in ("../logs/database.log", "crm.internal/logs/database.log"):
                    handler = RotatingFileHandler(path)
                    handler.close()

            frappe = SimpleNamespace(init=Mock(), connect=connect,
                get_installed_apps=Mock(return_value=["frappe", "crm"]), destroy=Mock())
            with chdir(bench), patch.dict(sys.modules, {"frappe": frappe}), patch("deployment.bootstrap.SITES", sites):
                self.assertEqual(installed_apps(), ["frappe", "crm"])
                self.assertEqual(Path.cwd(), bench)
            self.assertTrue((bench / "logs" / "database.log").exists())
            self.assertTrue((site_logs / "database.log").exists())
            frappe.init.assert_called_once_with(site="crm.internal", sites_path=str(sites))
            frappe.destroy.assert_called_once_with()

    def test_framework_failure_closes_context_and_restores_working_directory(self):
        for stage in ("init", "connect", "get_installed_apps"):
            with self.subTest(stage=stage), TemporaryDirectory() as tmp:
                sites = Path(tmp).resolve() / "sites"
                sites.mkdir()
                before = Path.cwd()
                frappe = SimpleNamespace(init=Mock(), connect=Mock(), get_installed_apps=Mock(), destroy=Mock())
                getattr(frappe, stage).side_effect = RuntimeError("database unavailable")
                with patch.dict(sys.modules, {"frappe": frappe}), patch("deployment.bootstrap.SITES", sites):
                    with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                        installed_apps()
                self.assertEqual(Path.cwd(), before)
                frappe.destroy.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
