"""Regression tests for fail-closed Docker privilege policy."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog import App
from privilege_policy import risky_settings, regressions


class PrivilegeRegressionTests(unittest.TestCase):
    def test_new_privileged_and_sensitive_bind_are_blocked(self):
        manifest = {"services": {"web": {
            "privileged": True,
            "cap_add": ["SYS_ADMIN"],
            "security_opt": ["seccomp:unconfined"],
            "volumes": ["/var/run/docker.sock:/var/run/docker.sock"],
        }}}
        warnings = risky_settings(manifest)
        self.assertEqual({row[1] for row in warnings},
                         {"privileged", "cap_add", "security_opt", "sensitive_mount"})
        app = App("new", Path("unused"), manifest, {})
        self.assertEqual(len(regressions([app], {})), 4)

    def test_baselined_legacy_permissions_not_silently_removed(self):
        manifest = {"services": {"web": {"privileged": True}}}
        app = App("existing", Path("unused"), manifest, {})
        self.assertEqual(regressions([app], {"existing": risky_settings(manifest)}), [])

    def test_safe_compose_does_not_trigger(self):
        manifest = {"services": {"web": {
            "read_only": True, "security_opt": ["no-new-privileges:true"],
            "volumes": ["/DATA/AppData/safe:/config:ro"],
        }}}
        self.assertFalse(risky_settings(manifest))
        app = App("safe", Path("unused"), manifest, {})
        self.assertFalse(regressions([app], {}))

    def test_new_host_network_is_blocked(self):
        manifest = {"services": {"web": {"network_mode": "host"}}}
        self.assertIn(("web", "network_mode", "host"), risky_settings(manifest))


    def _dozzle_migration(self):
        original = {"services": {"dozzle": {"volumes": [
            "/var/run/docker.sock:/var/run/docker.sock"]}}}
        revised = {
            "services": {
                "dozzle": {
                    "environment": [
                        "DOZZLE_REMOTE_HOST=tcp://dozzle-socket-proxy:2375",
                        "DOZZLE_ENABLE_ACTIONS=false", "DOZZLE_ENABLE_SHELL=false",
                    ],
                    "networks": ["default", "docker-api"],
                },
                "dozzle-socket-proxy": {
                    "image": "lscr.io/linuxserver/socket-proxy:latest@sha256:" + "a" * 64,
                    "read_only": True,
                    "tmpfs": ["/run"],
                    "security_opt": ["no-new-privileges:true"],
                    "environment": [
                        "CONTAINERS=1", "ALLOW_LOGS=1", "POST=0", "EXEC=0",
                        "BUILD=0", "AUTH=0", "SECRETS=0",
                    ],
                    "networks": ["docker-api"],
                    "volumes": [{
                        "type": "bind", "source": "/var/run/docker.sock",
                        "target": "/var/run/docker.sock", "read_only": True,
                    }],
                },
            },
            "networks": {"docker-api": {"internal": True}},
        }
        return original, revised

    def test_dozzle_migration_allows_only_relocated_socket(self):
        old, revised = self._dozzle_migration()
        app = App("dozzle", Path("unused"), revised, {})
        self.assertFalse(regressions([app], {"dozzle": risky_settings(old)}))

    def test_dozzle_proxy_exposing_api_is_blocked(self):
        old, revised = self._dozzle_migration()
        revised["services"]["dozzle-socket-proxy"]["ports"] = ["2375:2375"]
        app = App("dozzle", Path("unused"), revised, {})
        self.assertTrue(regressions([app], {"dozzle": risky_settings(old)}))

    def test_dozzle_proxy_enabling_posts_is_blocked(self):
        old, revised = self._dozzle_migration()
        p = revised["services"]["dozzle-socket-proxy"]
        p["environment"][2] = "POST=1"
        app = App("dozzle", Path("unused"), revised, {})
        self.assertTrue(regressions([app], {"dozzle": risky_settings(old)}))

    def test_other_app_cannot_use_dozzle_exception(self):
        old, revised = self._dozzle_migration()
        app = App("imposter", Path("unused"), revised, {})
        self.assertTrue(regressions([app], {"imposter": risky_settings(old)}))




if __name__ == "__main__":
    unittest.main()
