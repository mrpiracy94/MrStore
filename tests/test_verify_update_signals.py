"""Offline tests for real, monotonic ZimaOS v2 update signals."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_update_signals import verify

APP = "io.github.mrpiracy94.demo"


class UpdateSignalTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.previous = self.root / "before"
        self.dist = self.root / "after"
        self.previous.mkdir()
        self.dist.mkdir()
        self.report = self.root / "versions.json"

    def arrange(self, old_v="1.0.7", new_v="1.0.8",
                old_hash="ab123456", new_hash="cd123456",
                reason="approved-image-change"):
        (self.previous / "index.json").write_text(json.dumps({
            "apps": [{"id": APP, "version": old_v, "content_hash": old_hash}]}))
        (self.dist / "index.json").write_text(json.dumps({
            "apps": [{"id": APP, "version": new_v, "content_hash": new_hash}]}))
        self.report.write_text(json.dumps({"apps": [{
            "id": APP, "old": old_v, "new": new_v,
            "reason": reason}]}))

    def test_approved_new_image_advances_version_and_hash(self):
        self.arrange()
        self.assertEqual(verify(self.previous, self.dist, self.report)["verified_update_signals"], 1)

    def test_equal_hash_blocks_dishonest_update(self):
        self.arrange(new_hash="ab123456")
        with self.assertRaisesRegex(ValueError, "content_hash unchanged"):
            verify(self.previous, self.dist, self.report)

    def test_same_package_version_blocks_update_notice(self):
        self.arrange(new_v="1.0.7")
        with self.assertRaisesRegex(ValueError, "no higher package version"):
            verify(self.previous, self.dist, self.report)

    def test_retained_version_does_not_require_hash_change(self):
        self.arrange(new_v="1.0.7", new_hash="ab123456", reason="retained")
        self.assertEqual(verify(self.previous, self.dist, self.report)["verified_update_signals"], 0)

    def test_initial_digest_pin_can_change_hash_without_fake_bump(self):
        self.arrange(new_v="1.0.7", reason="initial-immutable-baseline")
        self.assertEqual(verify(self.previous, self.dist, self.report)["verified_update_signals"], 0)

    def test_explicit_source_bump_must_update_hash(self):
        self.arrange(reason="explicit-source-version")
        self.assertEqual(verify(self.previous, self.dist, self.report)["verified_update_signals"], 1)

    def test_version_regressions_fail(self):
        self.arrange(new_v="1.0.6", reason="retained")
        with self.assertRaisesRegex(ValueError, "went backwards"):
            verify(self.previous, self.dist, self.report)

    def test_missing_index_app_fails(self):
        self.arrange()
        (self.dist / "index.json").write_text('{"apps":[]}')
        with self.assertRaisesRegex(ValueError, "omitted"):
            verify(self.previous, self.dist, self.report)

    def test_missing_history_does_not_claim_actual_notification(self):
        self.arrange()
        (self.previous / "index.json").write_text('{"apps":[]}')
        self.assertEqual(verify(self.previous, self.dist, self.report)["without_active_previous_entry"], 1)

    def test_duplicate_changed_records_fail(self):
        self.arrange()
        report = json.loads(self.report.read_text())
        report["apps"].append(report["apps"][0])
        self.report.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            verify(self.previous, self.dist, self.report)


if __name__ == "__main__":
    unittest.main()
