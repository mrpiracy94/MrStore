"""Regression coverage for database/Redis-dependent MrStore entries.

These are assisted installs, not ZimaOS one-click or runtime-tested apps.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import apps
from compatibility import inspect_app


class ExternalDependenciesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = {x.folder: x for x in apps()}

    def test_hedgedoc_requires_real_database_and_hostname(self):
        item = self.entries["hedgedoc"]
        service = item.source["services"]["hedgedoc"]
        env = dict(v.split("=", 1) for v in service["environment"])
        fields = {v["container"] for v in service["x-casaos"]["envs"]}
        required = {"DB_HOST", "DB_PORT", "DB_USER", "DB_PASS", "DB_NAME",
                    "CMD_DOMAIN", "CMD_URL_ADDPORT", "CMD_PROTOCOL_USESSL"}
        self.assertTrue(required <= fields)
        self.assertEqual(env["DB_HOST"], "CHANGE_ME_DB_HOST")
        self.assertEqual(env["CMD_DOMAIN"], "CHANGE_ME_DOMAIN")
        self.assertNotIn("hedgedoc_db", item.source["services"])
        self.assertEqual(item.metadata["port_map"], "20029")
        self.assertTrue(any(v.get("target") == "/config" and
                            v.get("source") == "/DATA/AppData/hedgedoc/config"
                            for v in service["volumes"]))
        self.assertEqual(inspect_app(item)["status"], "configuration_required")

    def test_netbox_requires_external_postgres_and_redis(self):
        item = self.entries["netbox"]
        service = item.source["services"]["netbox"]
        env = dict(v.split("=", 1) for v in service["environment"])
        fields = {v["container"] for v in service["x-casaos"]["envs"]}
        mandatory = {"SUPERUSER_EMAIL", "SUPERUSER_PASSWORD", "ALLOWED_HOST",
                     "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME",
                     "REDIS_HOST", "REDIS_PORT", "REDIS_USERNAME", "REDIS_PASSWORD",
                     "REDIS_DB_TASK", "REDIS_DB_CACHE"}
        self.assertTrue(mandatory <= set(env))
        self.assertTrue(mandatory <= fields)
        self.assertEqual(env["DB_HOST"], "CHANGE_ME_DB_HOST")
        self.assertEqual(env["REDIS_HOST"], "CHANGE_ME_REDIS_HOST")
        self.assertNotEqual(env["ALLOWED_HOST"], "*")
        self.assertNotEqual(env["SUPERUSER_EMAIL"], "admin@example.com")
        self.assertEqual(env["REDIS_DB_TASK"], "0")
        self.assertEqual(env["REDIS_DB_CACHE"], "1")
        self.assertEqual(item.metadata["port_map"], "20048")
        self.assertEqual(inspect_app(item)["status"], "configuration_required")
        self.assertTrue(any(v.get("target") == "/config" and
                            v.get("source") == "/DATA/AppData/netbox/config"
                            for v in service["volumes"]))


if __name__ == "__main__":
    unittest.main()
