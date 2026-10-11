"""Regression tests for read-only upstream image comparison."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import upstream_image_audit as auditor

class UpstreamImageTests(unittest.TestCase):
    def test_real_apps_and_image_provenance(self):
        report = auditor.audit(ROOT)
        self.assertEqual(report["apps"], 254)
        self.assertEqual(report["unique_images"], 258)
        self.assertEqual(sum(report["publisher_classes"].values()), 258)
        self.assertEqual(report["publisher_classes"]["third_party_linuxserver"], 187)
        self.assertEqual(len(report["candidates"]), 6)
        for row in report["candidates"]:
            self.assertRegex(row["current_image"], auditor.PINNED)
            self.assertEqual(row["migration_status"], "needs_runtime_validation")

    def test_distinct_origin_classes(self):
        self.assertEqual(auditor.publisher_class("lscr.io/linuxserver/sonarr:latest"),
                         "third_party_linuxserver")
        self.assertEqual(auditor.publisher_class("ghcr.io/mrpiracy94/example:v1"),
                         "mrstore_rebuild")
        self.assertEqual(auditor.publisher_class("ghcr.io/vendor/example:v1"),
                         "publisher_not_verified")

    def test_lower_vulnerabilities_do_not_authorize_automatic_migration(self):
        item = {"app": "test", "current_image": "test/old:1@sha256:" + "a" * 64,
                "candidate_image": "test/new:1", "architectures": ["amd64"]}
        def simulate(image, arch):
            return {"critical": 0 if "new" in image else 5,
                    "high": 2 if "new" in image else 7}
        with patch.object(auditor, "resolve_digest",
                          return_value="test/new:1@sha256:" + "b" * 64), \
             patch.object(auditor, "trivy_counts", side_effect=simulate):
            report = auditor.compare(item)
        self.assertEqual(report["classification"], "candidate_lower_observed_cves")
        self.assertFalse(report["automatic_migration_allowed"])

    def test_require_improvement_on_every_architecture(self):
        item = {"app": "test", "current_image": "test/old:1@sha256:" + "a" * 64,
                "candidate_image": "test/new:1", "architectures": ["amd64", "arm64"]}
        def simulate(image, arch):
            return {"critical": 0 if "new" in image and arch == "amd64" else 3,
                    "high": 5}
        with patch.object(auditor, "resolve_digest",
                          return_value="test/new:1@sha256:" + "b" * 64), \
             patch.object(auditor, "trivy_counts", side_effect=simulate):
            report = auditor.compare(item)
        self.assertEqual(report["classification"], "not_better_on_all_architectures")

    def test_scanner_failure_is_never_a_clean_result(self):
        item = {"app": "test", "current_image": "test/old:1@sha256:" + "a" * 64,
                "candidate_image": "test/new:1", "architectures": ["amd64"]}
        with patch.object(auditor, "resolve_digest", side_effect=RuntimeError("registry 429")):
            report = auditor.compare(item)
        self.assertEqual(report["classification"], "inconclusive")
        self.assertFalse(report["automatic_migration_allowed"])

    def test_empty_trivy_report_rejected(self):
        with patch.object(auditor, "command", return_value='{"Results":[]}'):
            with self.assertRaises(ValueError):
                auditor.trivy_counts("a@sha256:" + "a" * 64, "amd64")

    def test_bad_candidate_reference_rejected(self):
        from catalog import apps
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Apps/test").mkdir(parents=True)
            (root / "data").mkdir()
            (root / "Apps/test/docker-compose.yml").write_text(
                "services:\n  test:\n    image: example:1@sha256:" + "a"*64 +
                "\nx-casaos:\n  id: test\n  architectures: [amd64]\n")
            (root / "data/upstream-candidates.json").write_text(json.dumps([{
                "app": "test", "service": "test",
                "candidate_image": "bad;touch /tmp/hack",
                "source_url": "https://github.com/vendor/example",
                "migration_status": "needs_runtime_validation",
                "migration_risk": "Manual migration"
            }]))
            with self.assertRaises(ValueError):
                auditor.candidates(root, apps(root))

if __name__ == "__main__":
    unittest.main()
