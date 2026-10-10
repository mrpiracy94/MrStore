"""Prevent unsafe/mutable image execution in live GitHub Actions pilot."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import yaml
from scripts.docker_live_pilot import validate_release, bounded_compose

IMAGE = "ghcr.io/mrpiracy94/mrstore-it-tools:test@sha256:" + "a"*64


class LiveDockerPilotTests(unittest.TestCase):
    def setUp(self):
        t = TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.manifest, self.selection, self.catalog = (root / n for n in ("compose.yml", "selection.json", "catalog.json"))
        self.compose = {
            "name": "it-tools",
            "services": {"it-tools": {"image": IMAGE, "container_name": "it-tools",
                "restart": "unless-stopped",
                "ports": [{"target": 80, "published": "30013", "protocol": "tcp"}],
                "x-casaos": {"envs": [], "ports": [], "volumes": []}}},
            "x-casaos": {"id": "io.github.mrpiracy94.it-tools",
                         "main": "it-tools", "architectures": ["amd64", "arm64"]},
        }
        self.selection.write_text(json.dumps({"approved": ["it-tools"], "approved_count": 1}))
        self.catalog.write_text(json.dumps({"approved_count": 1, "apps": [
            {"slug": "it-tools", "id": "io.github.mrpiracy94.it-tools"}]}))
        self.save()

    def save(self):
        self.manifest.write_text(yaml.safe_dump(self.compose))

    def test_safe_bound_install_uses_digest_localhost_no_volumes(self):
        approved = validate_release(self.manifest, self.selection, self.catalog)
        bounded = bounded_compose(approved, 59000)["services"]["it-tools"]
        self.assertEqual(bounded["ports"][0]["host_ip"], "127.0.0.1")
        self.assertNotIn("volumes", bounded)
        self.assertNotIn("environment", bounded)
        self.assertNotIn("privileged", bounded)
        self.assertTrue(bounded["image"].endswith("a"*64))

    def test_unapproved_app_does_not_execute(self):
        self.selection.write_text(json.dumps({"approved": ["other"], "approved_count": 1}))
        self.assertIsNone(validate_release(self.manifest, self.selection, self.catalog))

    def test_unsafe_fields_and_tag_rejected(self):
        for key, value in [
            ("volumes", ["/var/run/docker.sock:/var/run/docker.sock"]),
            ("privileged", True),
            ("environment", ["PASSWORD=secret"]),
            ("image", "nginx:latest"),
        ]:
            with self.subTest(key=key):
                old = self.compose["services"]["it-tools"].get(key)
                self.compose["services"]["it-tools"][key] = value
                self.save()
                with self.assertRaises(ValueError):
                    validate_release(self.manifest, self.selection, self.catalog)
                if old is None:
                    self.compose["services"]["it-tools"].pop(key)
                else:
                    self.compose["services"]["it-tools"][key] = old


if __name__ == "__main__":
    unittest.main()
