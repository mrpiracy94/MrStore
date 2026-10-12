"""Regression coverage for multi-architecture upstream image comparisons."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import upstream_image_audit as audit

ITEM = {"app": "sample", "current_image": "vendor/old@sha256:" + "a" * 64,
        "candidate_image": "vendor/new:stable", "architectures": ["amd64", "arm64"]}


class MultiarchTests(unittest.TestCase):
    def check(self, candidate_counts):
        def scanner(image, arch):
            if image == ITEM["current_image"]:
                return {"critical": 2, "high": 10}
            return candidate_counts[arch]
        with patch.object(audit, "resolve_digest", return_value="vendor/new:stable@sha256:" + "b" * 64), patch.object(audit, "trivy_counts", side_effect=scanner):
            return audit.compare(ITEM)

    def test_improvement_one_arch_unchanged_other(self):
        report = self.check({"amd64": {"critical": 1, "high": 9},
                             "arm64": {"critical": 2, "high": 10}})
        self.assertEqual(report["classification"], "candidate_lower_observed_cves")
        self.assertFalse(report["automatic_migration_allowed"])

    def test_regression_blocks(self):
        report = self.check({"amd64": {"critical": 1, "high": 9},
                             "arm64": {"critical": 2, "high": 11}})
        self.assertEqual(report["classification"], "not_better_on_all_architectures")

    def test_no_improvement_blocks(self):
        report = self.check({"amd64": {"critical": 2, "high": 10},
                             "arm64": {"critical": 2, "high": 10}})
        self.assertEqual(report["classification"], "not_better_on_all_architectures")

    def test_scan_failure_is_inconclusive(self):
        with patch.object(audit, "resolve_digest", side_effect=RuntimeError("429")):
            self.assertEqual(audit.compare(ITEM)["classification"], "inconclusive")
