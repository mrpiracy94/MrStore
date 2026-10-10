"""Host Docker API permissions cannot be evaded through parent/path aliases."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import App
from privilege_policy import risky_settings, regressions, sensitive_host_bind


class SensitiveHostBindTests(unittest.TestCase):
    def test_direct_ancestor_and_alias_socket_mounts_are_risky(self):
        exposed = [
            "/var/run/docker.sock", "//var/run/docker.sock",
            "/var/run/docker.sock/../docker.sock", "/var/run",
            "/run", "/var", "/var/lib", "/var/lib/docker",
            "/var/lib/docker/containers", "/run/containerd/containerd.sock",
            "/run/user/1000/docker.sock", "/root/.ssh",
            "/proc/1/root", "/sys/kernel", "/dev/kmsg",
        ]
        for source in exposed:
            with self.subTest(source=source):
                self.assertTrue(sensitive_host_bind(source))

    def test_ordinary_persistent_volumes_and_timezone_file_stay_allowed(self):
        benign = [
            "/DATA/AppData/immich/postgres", "/DATA/AppData/dockge/stacks",
            "/etc/localtime", "organizr-volume", "./config", "/mnt/media",
        ]
        for source in benign:
            with self.subTest(source=source):
                self.assertFalse(sensitive_host_bind(source))

    def test_short_and_long_form_binds_blocked(self):
        document = {"services": {
            "short": {"volumes": ["/var/run:/sock:ro"]},
            "long": {"volumes": [
                {"type": "bind", "source": "/var/lib/docker/containers",
                 "target": "/logs", "read_only": True}]},
            "safe": {"volumes": [
                {"type": "bind", "source": "/DATA/AppData/safe",
                 "target": "/config"}]},
        }}
        alerts = risky_settings(document)
        self.assertIn(("short", "sensitive_mount", "/var/run"), alerts)
        self.assertIn(("long", "sensitive_mount", "/var/lib/docker/containers"), alerts)
        self.assertFalse(any(row[0] == "safe" for row in alerts))

    def test_baselined_old_risk_is_not_confused_with_new_escalation(self):
        old = {"services": {"web": {"volumes": ["/var/run:/s"]}}}
        app = App("legacy", Path("unused"), old, {})
        baseline = {"legacy": risky_settings(old)}
        self.assertFalse(regressions([app], baseline))
        changed = {"services": {"web": {"volumes": ["/var/run:/s", "/root/.ssh:/keys"]}}}
        app_new = App("legacy", Path("unused"), changed, {})
        self.assertEqual(len(regressions([app_new], baseline)), 1)


if __name__ == "__main__":
    unittest.main()
