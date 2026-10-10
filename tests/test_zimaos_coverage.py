"""Device coverage must not certify tests from static checks or stale manifests."""
import json
from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog import apps
from zimaos_coverage import CHECK_NAMES, inventory, markdown


class DeviceCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = {app.folder: app for app in apps()}
        cls.example = cls.catalog["actual-budget"]

    def test_empty_registry_never_implies_device_evidence(self):
        # This must remain valid after genuine records are added to the repository.
        report = self.load_with()
        self.assertEqual(report["total_apps"], len(self.catalog))
        self.assertEqual(report["recorded_tests"], 0)
        self.assertEqual(report["apps_without_current_device_evidence"], len(self.catalog))
        self.assertEqual(report["c3_all_declared_architectures"], 0)
        self.assertEqual(len(report["apps"]), len(self.catalog))
        self.assertIn("não certificados automaticamente", markdown(report))

    def sample_record(self, level="C3"):
        yes = {"runtime_observed", "ui_or_service_checked"}
        if level in ("C3", "C4"):
            yes |= {"installed_from_mrstore", "core_function_checked", "restart_persistence_checked"}
        if level == "C4":
            yes |= {"backup_checked", "upgrade_checked", "restore_checked", "rollback_checked"}
        return {
            "app": self.example.folder,
            "architecture": self.example.metadata["architectures"][0],
            "zimaos_version": "1.5.0",
            "tested_at": date.today().isoformat(),
            "compose_sha256": sha256(self.example.path.read_bytes()).hexdigest(),
            "image_ref": "example/image:1.2.3",
            "level": level,
            "evidence_url": "https://github.com/mrpiracy94/MrStore/issues/45",
            "checks": {key: key in yes for key in CHECK_NAMES},
        }

    def load_with(self, *records):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "device-tests.json"
            path.write_text(json.dumps({"schema": 1, "tests": list(records)}), encoding="utf-8")
            return inventory(registry_path=path)

    def test_evidence_is_architecture_specific(self):
        report = self.load_with(self.sample_record("C3"))
        entry = next(x for x in report["apps"] if x["app"] == self.example.folder)
        self.assertEqual(report["apps_with_current_device_evidence"], 1)
        self.assertEqual(report["c3_any_architecture"], 1)
        self.assertEqual(report["c3_all_declared_architectures"],
                         int(len(self.example.metadata["architectures"]) == 1))
        self.assertEqual(entry["levels_by_architecture"][self.example.metadata["architectures"][0]], "C3")

    def test_manifest_change_invalidates_current_coverage(self):
        old = self.sample_record("C4")
        old["compose_sha256"] = "0" * 64
        report = self.load_with(old)
        self.assertEqual(report["stale_records"], 1)
        self.assertEqual(report["apps_with_current_device_evidence"], 0)
        self.assertEqual(report["c4_all_declared_architectures"], 0)

    def test_c3_requires_real_function_and_persistence_checks(self):
        invalid = self.sample_record("C3")
        invalid["checks"]["restart_persistence_checked"] = False
        with self.assertRaisesRegex(ValueError, "lacks required checks"):
            self.load_with(invalid)

    def test_unknown_app_or_unsupported_architecture_is_rejected(self):
        bad = self.sample_record()
        bad["app"] = "nonexistent"
        with self.assertRaisesRegex(ValueError, "unknown catalog app"):
            self.load_with(bad)
        bad = self.sample_record()
        bad["architecture"] = "mips"
        with self.assertRaisesRegex(ValueError, "architecture not declared"):
            self.load_with(bad)

    def test_external_evidence_urls_are_rejected(self):
        bad = self.sample_record()
        bad["evidence_url"] = "https://example.com/private-key"
        with self.assertRaisesRegex(ValueError, "evidence must link"):
            self.load_with(bad)

    def test_boolean_checks_do_not_accept_strings(self):
        bad = self.sample_record()
        bad["checks"]["runtime_observed"] = "true"
        with self.assertRaisesRegex(ValueError, "must be booleans"):
            self.load_with(bad)


if __name__ == "__main__":
    unittest.main()
