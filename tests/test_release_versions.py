"""Regression tests for visible, truthful and monotonic ZimaOS package updates."""
import json
from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from release_versions import promote


def sample(version, image):
    return {
        "name": "demo",
        "services": {"demo": {"image": image}},
        "x-casaos": {"id": "io.github.mrpiracy94.demo", "version": version,
                     "main": "demo", "update_at": "2026-10-09"},
    }


class ReleaseVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stage = self.root / "stage"
        self.previous = self.root / "previous"
        self.staged_file = self.stage / "Apps" / "demo" / "docker-compose.yml"
        self.staged_file.parent.mkdir(parents=True)
        self.old_compose = self.previous / "apps" / "io.github.mrpiracy94.demo" / "docker-compose.yml"
        self.old_compose.parent.mkdir(parents=True)
        self.old_meta = self.old_compose.parent / "meta.json"

    def prepare(self, old_version="1.0.7", old_image="example/demo:latest",
                new_version="1.0.0", new_image=None):
        if new_image is None:
            new_image = old_image
        self.staged_file.write_text(yaml.safe_dump(sample(new_version, new_image)))
        self.old_compose.write_text(yaml.safe_dump(sample(old_version, old_image)))
        (self.previous / "index.json").write_text(json.dumps({
            "apps": [{"id": "io.github.mrpiracy94.demo", "version": old_version}]
        }))
        self.old_meta.write_text(json.dumps({
            "version": old_version, "update_at": "2026-09-15",
            "release_note": "Previous approved release.",
        }))

    def test_image_change_advances_published_version_and_records_reason(self):
        self.prepare(old_image="example/demo:latest@sha256:" + "a" * 64,
                     new_image="example/demo:latest@sha256:" + "b" * 64)
        result = promote(self.stage, self.previous, today=date(2026, 10, 10))
        current = yaml.safe_load(self.staged_file.read_text())["x-casaos"]
        self.assertEqual(current["version"], "1.0.8")
        self.assertEqual(result["image_updates"], 1)
        self.assertEqual(result["apps"][0]["changed_services"], ["demo"])
        self.assertIn("release security gate", current["release_notes"]["en_US"])
        self.assertEqual(current["update_at"], "2026-10-10")

    def test_same_images_do_not_generate_false_update_or_regress_version(self):
        self.prepare()
        report = promote(self.stage, self.previous, today=date(2026, 10, 10))
        current = yaml.safe_load(self.staged_file.read_text())["x-casaos"]
        self.assertEqual(current["version"], "1.0.7")
        self.assertEqual(current["update_at"], "2026-09-15")
        self.assertEqual(report["carried_forward"], 1)
        self.assertEqual(report["image_updates"], 0)

    def test_manual_semver_increase_is_respected(self):
        self.prepare(new_version="1.2.0", new_image="example/demo:latest@sha256:" + "b" * 64)
        report = promote(self.stage, self.previous, today=date(2026, 10, 10))
        self.assertEqual(yaml.safe_load(self.staged_file.read_text())["x-casaos"]["version"], "1.2.0")
        self.assertEqual(report["image_updates"], 0)
        self.assertEqual(report["explicit_updates"], 1)

    def test_first_digest_pin_is_not_a_fictitious_update(self):
        self.prepare(old_version="1.0.7", old_image="example/demo:latest",
                     new_version="1.0.0",
                     new_image="example/demo:latest@sha256:" + "a" * 64)
        report = promote(self.stage, self.previous, today=date(2026, 10, 10))
        current = yaml.safe_load(self.staged_file.read_text())["x-casaos"]
        self.assertEqual(current["version"], "1.0.7")
        self.assertEqual(current["update_at"], "2026-09-15")
        self.assertEqual(report["image_updates"], 0)
        self.assertEqual(report["baseline_pins"], 1)
        self.assertEqual(report["apps"][0]["changed_services"], [])
        self.assertEqual(report["apps"][0]["baseline_services"], ["demo"])
        self.assertEqual(report["state"]["apps"]["io.github.mrpiracy94.demo"]["images"]["demo"],
                         "example/demo:latest@sha256:" + "a" * 64)

    def test_reject_loss_of_immutable_reference(self):
        self.prepare(old_image="example/demo:latest@sha256:" + "a" * 64,
                     new_image="example/demo:latest")
        with self.assertRaisesRegex(ValueError, "refusing to downgrade immutable"):
            promote(self.stage, self.previous, today=date(2026, 10, 10))

    def test_newly_published_app_keeps_original_version(self):
        self.staged_file.write_text(yaml.safe_dump(sample("1.0.0", "example/demo:1")))
        (self.previous / "index.json").write_text('{"apps": []}')
        report = promote(self.stage, self.previous, today=date(2026, 10, 10))
        self.assertEqual(report["new_to_store"], 1)
        self.assertEqual(yaml.safe_load(self.staged_file.read_text())["x-casaos"]["version"], "1.0.0")

    def test_reappearing_quarantined_app_keeps_its_last_version(self):
        old_digest = "example/demo:latest@sha256:" + "a" * 64
        new_digest = "example/demo:latest@sha256:" + "b" * 64
        self.staged_file.write_text(yaml.safe_dump(sample("1.0.0", new_digest)))
        # App was quarantined from the previous index but remains in the version ledger.
        (self.previous / "index.json").write_text('{"apps": []}')
        (self.previous / "release-versions-state.json").write_text(json.dumps({
            "schema": 1,
            "apps": {"io.github.mrpiracy94.demo": {
                "version": "1.0.7", "images": {"demo": old_digest},
                "update_at": "2026-09-15", "release_note": "Older safe release."
            }},
        }))
        report = promote(self.stage, self.previous, today=date(2026, 10, 10))
        self.assertEqual(report["image_updates"], 1)
        self.assertEqual(report["state"]["apps"]["io.github.mrpiracy94.demo"]["version"], "1.0.8")
        self.assertEqual(yaml.safe_load(self.staged_file.read_text())["x-casaos"]["version"], "1.0.8")

    def test_missing_previous_publish_fails_closed(self):
        self.staged_file.write_text(yaml.safe_dump(sample("1.0.0", "example/demo:1")))
        with self.assertRaisesRegex(ValueError, "Previous published index"):
            promote(self.stage, self.previous, today=date(2026, 10, 10))

    def test_corrupt_previous_compose_fails_closed(self):
        self.prepare()
        self.old_compose.unlink()
        with self.assertRaisesRegex(ValueError, "previous published compose"):
            promote(self.stage, self.previous, today=date(2026, 10, 10))

    def test_non_semver_versions_fail_instead_of_disappearing_from_index(self):
        self.prepare(old_version="latest")
        with self.assertRaisesRegex(ValueError, "non-semver"):
            promote(self.stage, self.previous, today=date(2026, 10, 10))


if __name__ == "__main__":
    unittest.main()
