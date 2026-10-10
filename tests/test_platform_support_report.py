"""No platform can advertise unapproved or stale package counts."""
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from scripts.platform_support_report import report


class SupportMatrixTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.dist = self.root / "dist"
        (self.dist / "universal/compose").mkdir(parents=True)
        (self.dist / "universal/compose/demo.yml").write_text("name: demo")
        (self.dist / "universal/catalog.json").write_text(json.dumps({
            "version": 1, "approved_count": 1, "apps": [{"slug": "demo"}]}))
        self.selection = self.root / "selection.json"
        self.selection.write_text(json.dumps({"approved": ["demo"], "approved_count": 1}))

    def test_reports_eleven_without_falsely_claiming_runtime(self):
        data = report(self.selection, self.dist)
        self.assertEqual(len(data["systems"]), 11)
        self.assertFalse(data["runtime_tested"])
        self.assertTrue(all(not item["native_certified"] for item in data["systems"]))
        self.assertTrue(all(item["runtime_verified_count"] == 0 for item in data["systems"]))
        self.assertEqual(next(s for s in data["systems"] if s["id"] == "portainer")
                         ["format_eligible_count"], 1)
        self.assertEqual(next(s for s in data["systems"] if s["id"] == "olares")
                         ["format_eligible_count"], 0)

    def test_rejects_unapproved_seed_zip(self):
        (self.dist / "store").mkdir()
        with ZipFile(self.dist / "store/umbrel-community-preview.zip", "w") as z:
            z.writestr("mrstore-rogue/umbrel-app.yml", "id: mrstore-rogue")
        with self.assertRaisesRegex(ValueError, "outside"):
            report(self.selection, self.dist)

    def test_rejects_mismatched_homeio_source(self):
        (self.dist / "store").mkdir()
        with ZipFile(self.dist / "store/casaos-homeio-preview.zip", "w") as z:
            z.writestr("Apps/rogue/docker-compose.yml", "services: {}")
        with self.assertRaisesRegex(ValueError, "differs"):
            report(self.selection, self.dist)

    def test_rejects_stale_homedock_report(self):
        (self.dist / "homedock").mkdir()
        (self.dist / "homedock/catalog.json").write_text(json.dumps({
            "source_approved": 254, "packages": [{"slug": "demo"}]}))
        with self.assertRaisesRegex(ValueError, "stale"):
            report(self.selection, self.dist)


if __name__ == "__main__":
    unittest.main()
