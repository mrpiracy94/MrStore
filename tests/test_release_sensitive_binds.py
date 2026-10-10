"""Regression checks: release quarantine must reject dangerous bind aliases."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from release_catalog import insecure_defaults


class ReleaseSensitiveBindTests(unittest.TestCase):
    def check_mount(self, source, blocked):
        app = SimpleNamespace(source={"services": {"web": {
            "image": "example/image:1", "volumes": [f"{source}:/host:ro"]
        }}})
        findings = insecure_defaults(app)
        self.assertEqual(bool(findings), blocked, (source, findings))

    def test_sensitive_ancestors_and_aliases(self):
        for source in ("/var/run", "/var", "/var/run/docker.sock",
                       "/run/docker.sock", "/etc/ssh", "/root/.ssh",
                       "/var/lib/docker", "/etc/../etc/shadow"):
            with self.subTest(source=source):
                self.check_mount(source, True)

    def test_regular_data_volumes_are_allowed(self):
        for source in ("/DATA/AppData/example", "/mnt/media", "./config"):
            with self.subTest(source=source):
                self.check_mount(source, False)


if __name__ == "__main__":
    unittest.main()
