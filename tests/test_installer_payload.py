"""Generated ZimaOS v2 build must preserve mandatory credential guards."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_installer_payload import inspect_built


class PublishedSecretsTests(unittest.TestCase):
    def _fixture(self, parent: Path):
        app = parent / "Apps" / "demo"
        app.mkdir(parents=True)
        source = {
            "services": {"demo": {"image": "example/demo:1",
                                  "environment": ["KEY=${EXAMPLE_KEY:?required}"]}},
            "x-casaos": {"id": "example.demo"},
        }
        (app / "docker-compose.yml").write_text(yaml.safe_dump(source), encoding="utf-8")
        folder = parent / "dist" / "apps" / "example.demo"
        folder.mkdir(parents=True)
        built = {"services": source["services"], "x-casaos": {"id": "example.demo"}}
        (folder / "docker-compose.yml").write_text(yaml.safe_dump(built), encoding="utf-8")
        (folder / "meta.json").write_text(json.dumps({
            "tips": {"before_install": "Set EXAMPLE_KEY before installing"}
        }), encoding="utf-8")
        return folder

    def test_valid_published_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root)
            output = inspect_built(root)
            self.assertEqual(output["passed"], 1)
            self.assertEqual(output["failed"], 0)
            self.assertFalse(output["zimaos_runtime_verified"])

    def test_builder_dropping_required_variable_fails_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = self._fixture(root)
            manifest = folder / "docker-compose.yml"
            text = manifest.read_text().replace("${EXAMPLE_KEY:?required}", "plain-text")
            manifest.write_text(text)
            output = inspect_built(root)
            self.assertEqual(output["failed"], 1)
            self.assertIn("required environment", output["results"][0]["errors"][0])

    def test_builder_dropping_preinstall_warning_fails_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = self._fixture(root)
            (folder / "meta.json").write_text(json.dumps({"tips": {}}))
            output = inspect_built(root)
            self.assertEqual(output["failed"], 1)
            self.assertIn("warning missing", output["results"][0]["errors"][0])


if __name__ == "__main__":
    unittest.main()
