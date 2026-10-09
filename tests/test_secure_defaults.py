"""Regressions for removing optional host privileges and ensuring setup is editable.

No NAS execution or image scanning is implied by this suite.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import apps, report


def environment(service):
    raw = service.get("environment") or []
    if isinstance(raw, dict):
        return raw
    return dict(item.split("=", 1) for item in raw if isinstance(item, str) and "=" in item)


def editable(service):
    return {item["container"] for item in service["x-casaos"].get("envs", [])}


class SecureDefaultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = {item.folder: item for item in apps()}

    def test_optional_docker_sock_is_not_mounted(self):
        for name in ("glances", "homepage", "homarr"):
            with self.subTest(app=name):
                app = self.items[name]
                service = app.source["services"][name]
                volumes = service.get("volumes") or []
                self.assertFalse(any(
                    (volume.get("source") == "/var/run/docker.sock"
                     or volume.get("target") == "/var/run/docker.sock")
                    if isinstance(volume, dict)
                    else "/var/run/docker.sock" in str(volume)
                    for volume in volumes))
                defined = service.get("x-casaos", {}).get("volumes", [])
                self.assertFalse(any(item.get("container") == "/var/run/docker.sock"
                                     for item in defined))
                self.assertNotEqual(app.metadata["version"], "1.0.0")

    def test_docker_socket_dependents_remain_unchanged(self):
        # Do not disable the core functionality of apps that require Docker.
        for name in ("dozzle", "dockge", "socket-proxy"):
            with self.subTest(app=name):
                services = self.items[name].source["services"].values()
                self.assertTrue(any(
                    any(v.get("source") == "/var/run/docker.sock"
                        for v in service.get("volumes", []) if isinstance(v, dict))
                    for service in services))

    def test_homepage_rejects_wildcard_host_by_default(self):
        app = self.items["homepage"]
        env = environment(app.source["services"]["homepage"])
        self.assertNotIn("*", env["HOMEPAGE_ALLOWED_HOSTS"])
        self.assertEqual(env["HOMEPAGE_ALLOWED_HOSTS"], "zimaos.local:30007")
        self.assertIn("HOMEPAGE_ALLOWED_HOSTS", editable(app.source["services"]["homepage"]))
        self.assertEqual(app.metadata["port_map"], "30007")

    def test_homarr_retains_encryption_key_and_persistent_data(self):
        service = self.items["homarr"].source["services"]["homarr"]
        self.assertEqual(environment(service)["SECRET_ENCRYPTION_KEY"], "CHANGE_ME_64_HEX")
        self.assertIn("SECRET_ENCRYPTION_KEY", editable(service))
        self.assertTrue(any(v.get("source") == "/DATA/AppData/homarr"
                            and v.get("target") == "/appdata"
                            for v in service["volumes"]))
        self.assertEqual(self.items["homarr"].metadata["port_map"], "7575")

    def test_duckdns_never_uses_unregistered_example_subdomain(self):
        service = self.items["duckdns"].source["services"]["duckdns"]
        env = environment(service)
        self.assertEqual(env["SUBDOMAINS"], "CHANGE_ME_SUBDOMAIN")
        self.assertEqual(env["TOKEN"], "CHANGE_ME")
        self.assertTrue({"SUBDOMAINS", "TOKEN"} <= editable(service))
        self.assertEqual(self.items["duckdns"].metadata["port_map"], "0")

    def test_healthchecks_mandatory_upstream_secrets_cannot_be_hidden(self):
        app = self.items["healthchecks"]
        service = app.source["services"]["healthchecks"]
        env = environment(service)
        required = {"SECRET_KEY", "SITE_ROOT", "SITE_NAME",
                    "SUPERUSER_EMAIL", "SUPERUSER_PASSWORD"}
        self.assertTrue(required <= set(env))
        self.assertTrue(required <= editable(service))
        self.assertEqual(env["SITE_ROOT"], "http://zimaos.local:20037")
        self.assertNotEqual(env["SUPERUSER_EMAIL"], "admin@example.com")
        self.assertIn("CHANGE_ME", env["SUPERUSER_PASSWORD"])
        self.assertIn("CHANGE_ME", env["SECRET_KEY"])
        self.assertEqual(app.metadata["port_map"], "20037")
        self.assertTrue(any(v.get("source") == "/DATA/AppData/healthchecks/config"
                            and v.get("target") == "/config"
                            for v in service["volumes"]))

    def test_sensitive_mount_count_is_reduced_without_hiding_warnings(self):
        findings = report()["findings"]
        unsafe = {i["app"] for i in findings if i["code"] == "sensitive_mount"}
        self.assertFalse(unsafe & {"glances", "homepage", "homarr"})
        self.assertTrue({"dozzle", "dockge", "netdata", "socket-proxy"} <= unsafe)


if __name__ == "__main__":
    unittest.main()
