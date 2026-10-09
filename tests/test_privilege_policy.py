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


if __name__ == "__main__":
    unittest.main()
