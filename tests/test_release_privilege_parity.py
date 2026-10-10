"""Release quarantine must never be weaker than the PR host-privilege gate."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog import report
from privilege_policy import risky_settings, sensitive_host_bind
from release_catalog import insecure_defaults


def app_with(service):
    return SimpleNamespace(source={"services": {"web": {"image": "example/app:1", **service}}})


class PrivilegeReleaseParityTests(unittest.TestCase):
    def test_every_pr_host_risk_is_quarantined_for_release(self):
        configs = [
            {"volumes": ["/var/run:/s:ro"]},
            {"volumes": [{"type": "bind", "source": "/var/lib/docker/containers", "target": "/logs", "read_only": True}]},
            {"volumes": ["/run/user/1000/docker.sock:/socket:ro"]},
            {"volumes": ["/root/.ssh:/keys:ro"]},
            {"volumes": ["/etc/docker/daemon.json:/config:ro"]},
            {"volumes": ["/run/containerd/containerd.sock:/socket:ro"]},
            {"volumes": ["/etc/shadow:/shadow:ro"]},
            {"privileged": True},
            {"network_mode": "host"},
            {"pid": "host"},
            {"ipc": "host"},
            {"uts": "host"},
            {"user": "root"},
            {"user": "0:0"},
            {"cap_add": ["SYS_ADMIN"]},
            {"devices": ["/dev/kvm:/dev/kvm"]},
            {"security_opt": ["seccomp:unconfined"]},
            {"security_opt": ["apparmor:unconfined"]},
            {"security_opt": ["no-new-privileges:false"]},
        ]
        for config in configs:
            with self.subTest(config=config):
                app = app_with(config)
                self.assertTrue(risky_settings(app.source), config)
                reasons = insecure_defaults(app)
                self.assertTrue(any("dangerous" in item for item in reasons), reasons)

    def test_user_namespace_host_cannot_pass(self):
        self.assertTrue(any("userns" in r for r in
                            insecure_defaults(app_with({"userns": "host"}))))

    def test_readonly_flag_does_not_make_docker_socket_safe(self):
        service = {"volumes": [{"type": "bind",
                                "source": "/var/run/docker.sock",
                                "target": "/var/run/docker.sock",
                                "read_only": True}]}
        self.assertTrue(insecure_defaults(app_with(service)))

    def test_allowed_storage_paths_are_not_quarantined(self):
        source = {"volumes": [
            "/DATA/AppData/example:/data",
            "/etc/localtime:/etc/localtime:ro",
            {"type": "volume", "source": "private-cache", "target": "/cache"},
            "/mnt/media:/media:ro",
        ]}
        self.assertFalse(risky_settings(app_with(source).source))
        self.assertEqual(insecure_defaults(app_with(source)), [])

    def test_static_report_flags_aliases_and_parents(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp) / "Apps" / "sample"
            app_dir.mkdir(parents=True)
            # Only asserted on sensitive_mount; unrelated metadata rules can warn.
            (app_dir / "docker-compose.yml").write_text(
                "name: sample\nservices:\n  sample:\n"
                "    image: example/app:1\n"
                "    volumes:\n"
                "      - /var/run:/host-run:ro\n"
                "      - /run/user/1000/docker.sock:/sock:ro\n"
                "      - /etc/localtime:/etc/localtime:ro\n"
                "x-casaos:\n  id: io.github.example.sample\n",
                encoding="utf-8",
            )
            findings = report(Path(tmp))["findings"]
            unsafe = [f["message"] for f in findings if f["code"] == "sensitive_mount"]
            self.assertEqual(len(unsafe), 2, unsafe)
            self.assertTrue(any("/var/run" in v for v in unsafe))
            self.assertTrue(any("/run/user/1000/docker.sock" in v for v in unsafe))
            self.assertFalse(sensitive_host_bind("/etc/localtime"))


if __name__ == "__main__":
    unittest.main()
