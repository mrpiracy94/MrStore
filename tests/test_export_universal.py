"""Offline regression checks for safe universal archive export."""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from scripts.export_universal import export

SHA = "a" * 64


class UniversalExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "release-source"
        app = self.source / "Apps" / "demo"
        app.mkdir(parents=True)
        (app / "docker-compose.yml").write_text(
            "name: demo\nservices:\n  web:\n"
            f"    image: example/demo@sha256:{SHA}\n"
            "    ports:\n      - '8080:8080'\n"
            "x-casaos:\n  id: io.github.mrpiracy94.demo\n"
            "  main: web\n  title:\n    en_US: Demo\n",
            encoding="utf-8")
        for name in ("store-config.json", "supported-languages.json",
                     "category-list.json", "recommend-list.json"):
            (self.source / name).write_text("[]", encoding="utf-8")
        self.selection = self.root / "release-selection.json"
        self.selection.write_text(json.dumps({"approved_count": 1, "approved": ["demo"]}),
                                  encoding="utf-8")
        self.output = self.root / "dist" / "store" / "casaos-homeio-preview.zip"

    def test_export_contains_only_approved_digest_pinned_apps(self):
        self.assertEqual(export(self.source, self.selection, self.output), 1)
        with ZipFile(self.output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn("Apps/demo/docker-compose.yml", archive.namelist())
            self.assertEqual(len([x for x in archive.namelist()
                                  if x.endswith("/docker-compose.yml")]), 1)

    def test_unapproved_app_fail_closed(self):
        rogue = self.source / "Apps" / "rogue"
        rogue.mkdir()
        (rogue / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differ"):
            export(self.source, self.selection, self.output)
        self.assertFalse(self.output.exists())

    def test_reject_unpinned_image(self):
        path = self.source / "Apps" / "demo" / "docker-compose.yml"
        path.write_text(path.read_text().replace(f"@sha256:{SHA}", ":latest"))
        with self.assertRaisesRegex(ValueError, "not pinned"):
            export(self.source, self.selection, self.output)

    def test_reject_unconfigured_secret(self):
        path = self.source / "Apps" / "demo" / "docker-compose.yml"
        path.write_text(path.read_text().replace(
            "    ports:", "    environment:\n      - PASS=CHANGE_ME\n    ports:"))
        with self.assertRaisesRegex(ValueError, "unresolved secret"):
            export(self.source, self.selection, self.output)

    def test_reject_symlink(self):
        app = self.source / "Apps" / "demo"
        (app / "unsafe.yml").symlink_to(self.selection)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            export(self.source, self.selection, self.output)

    def test_reject_fake_approval_count(self):
        self.selection.write_text(json.dumps({"approved_count": 254, "approved": ["demo"]}))
        with self.assertRaisesRegex(ValueError, "approval evidence"):
            export(self.source, self.selection, self.output)


if __name__ == "__main__":
    unittest.main()
