"""Certification evidence stays empty until *reviewed* real device proof exists."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.universal_device_coverage import inventory


class DeviceCoverageTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        path = self.root / "Apps/demo/docker-compose.yml"
        path.parent.mkdir(parents=True)
        path.write_text("services:\n  web:\n    image: example@sha256:" + "a"*64 + "\n")
        self.sha = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.root / "data").mkdir()
        self.registry = self.root / "data/universal-device-tests.json"
        self.write([])

    def write(self, records):
        self.registry.write_text(json.dumps({
            "schema": 1, "description": "Real device tests", "tests": records}))

    def record(self):
        return {
            "app": "demo", "platform": "docker-linux", "platform_version": "27.0",
            "architecture": "amd64", "tested_at": "2026-10-10",
            "compose_sha256": self.sha,
            "evidence_url": "https://github.com/mrpiracy94/MrStore/issues/100",
            "reviewed_by": ["reviewer-one", "reviewer-two"],
            "checks": {k: True for k in (
                "native_import", "installed_on_target", "core_function",
                "restart_persistence", "upgrade", "backup_restore", "rollback",
                "security_review")},
        }

    def test_empty_not_fake_certified(self):
        report = inventory(self.root)
        self.assertEqual(len(report["platforms"]), 11)
        self.assertFalse(report["all_eleven_have_c4_evidence"])
        self.assertTrue(all(x["c4_upgrade_restore_app_arch_pairs"] == 0
                            for x in report["platforms"]))

    def test_reviewed_complete_record_only_claims_community_c4(self):
        record = self.record()
        self.write([record])
        report = inventory(self.root)
        target = next(x for x in report["platforms"] if x["id"] == "docker-linux")
        self.assertEqual(target["c4_apps"], ["demo"])
        self.assertFalse(target["vendor_certified"])
        self.assertFalse(report["all_eleven_have_c4_evidence"])

    def test_stale_digest_not_counted(self):
        record = self.record()
        record["compose_sha256"] = "b"*64
        self.write([record])
        report = inventory(self.root)
        self.assertEqual(report["stale_records"], 1)
        self.assertEqual(report["current_evidence_records"], 0)

    def test_rejects_one_reviewer_fake_boolean_future_date(self):
        for issue in ("reviews", "checks", "date"):
            record = self.record()
            if issue == "reviews":
                record["reviewed_by"] = ["same", "same"]
            elif issue == "checks":
                record["checks"]["upgrade"] = "yes"
            else:
                record["tested_at"] = "2099-01-01"
            with self.subTest(issue=issue):
                self.write([record])
                with self.assertRaises(ValueError):
                    inventory(self.root)

    def test_partial_level_does_not_become_c4(self):
        record = self.record()
        record["checks"]["rollback"] = False
        self.write([record])
        report = inventory(self.root)
        target = next(x for x in report["platforms"] if x["id"] == "docker-linux")
        self.assertEqual(target["c3_functional_app_arch_pairs"], 1)
        self.assertEqual(target["c4_upgrade_restore_app_arch_pairs"], 0)


if __name__ == "__main__":
    unittest.main()
