"""Portable catalog is sourced only from the security-approved release."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.export_portable_catalog import build, portainer_template, PLATFORMS

SHA = "b" * 64


class PortableCatalogTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.source = self.root / "release-source"
        app = self.source / "Apps" / "example"
        app.mkdir(parents=True)
        (app / "docker-compose.yml").write_text(
            f"name: example\nservices:\n  web:\n    image: example/image@sha256:{SHA}\n"
            "x-casaos:\n  id: io.github.mrpiracy94.example\n"
            "  main: web\n  category: Home\n  title:\n    en_US: Example App\n"
        )
        for name in ("store-config.json", "supported-languages.json",
                     "category-list.json", "recommend-list.json"):
            (self.source / name).write_text("[]")
        self.selection = self.root / "selected.json"
        self.selection.write_text(json.dumps(
            {"approved": ["example"], "approved_count": 1}))
        self.dist = self.root / "dist"

    def test_all_eleven_platforms_and_approved_compose(self):
        result = build(self.source, self.selection, self.dist)
        self.assertEqual(len(PLATFORMS), 11)
        self.assertEqual(len(result["platforms"]), 11)
        self.assertEqual(result["approved_count"], 1)
        self.assertEqual(result["apps"][0]["title"], "Example App")
        self.assertEqual((self.dist / "universal/compose/example.yml").read_text(),
                         (self.source / "Apps/example/docker-compose.yml").read_text())
        stored = json.loads((self.dist / "universal/catalog.json").read_text())
        self.assertEqual(stored["apps"], result["apps"])
        templates = json.loads((self.dist / "universal/portainer-templates.json").read_text())
        self.assertEqual(templates["version"], "2")
        self.assertEqual(templates["templates"][0]["type"], 1)

    def test_reject_unapproved_addition(self):
        (self.source / "Apps" / "rogue").mkdir()
        with self.assertRaises(ValueError):
            build(self.source, self.selection, self.dist)
        self.assertFalse((self.dist / "universal").exists())

    def test_reject_unscanned_tag_and_preserve_output(self):
        compose = self.source / "Apps/example/docker-compose.yml"
        compose.write_text(compose.read_text().replace(f"@sha256:{SHA}", ":latest"))
        with self.assertRaises(ValueError):
            build(self.source, self.selection, self.dist)
        self.assertFalse((self.dist / "universal").exists())

    def test_portainer_restricted_template_schema(self):
        example = {
            "services": {"main": {
                "image": "example/img@sha256:" + SHA,
                "environment": ["TZ=Europe/Lisbon"],
                "ports": [{"published": "8080", "target": 80, "protocol": "tcp"}],
                "volumes": [{"type": "bind", "source": "/DATA/AppData/example",
                             "target": "/data", "read_only": True}],
                "restart": "unless-stopped",
            }},
            "x-casaos": {"title": {"en_US": "Example"}, "category": "Home"}
        }
        template = portainer_template("example", example)
        self.assertEqual(template["type"], 1)
        self.assertEqual(template["ports"], ["8080:80/tcp"])
        self.assertEqual(template["volumes"][0]["container"], "/data")
        self.assertEqual(template["image"], "example/img@sha256:" + SHA)
        example["services"]["database"] = {"image": "example/db@sha256:" + SHA}
        self.assertIsNone(portainer_template("example", example))
        example["services"].pop("database")
        example["services"]["main"]["privileged"] = True
        self.assertIsNone(portainer_template("example", example))

    def test_no_overwrite(self):
        build(self.source, self.selection, self.dist)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            build(self.source, self.selection, self.dist)


if __name__ == "__main__":
    unittest.main()
