"""Regression tests for safe same-vendor digest CVE comparisons."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cve_digest_refresh as audit

SHA = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64

def sample():
    return {"app": "example", "service": "example",
            "compose_path": "Apps/example/docker-compose.yml",
            "current_image": "vendor/example:latest@" + SHA,
            "tag": "vendor/example:latest", "current_digest": SHA,
            "architectures": ["amd64", "arm64"]}

class RefreshTests(unittest.TestCase):
    def test_all_existing_apps_remain_pinned(self):
        for name in ("qbittorrent", "freshrss", "obsidian", "homarr", "glances", "rpcs3"):
            item = audit.get_item(ROOT, name)
            self.assertEqual(item["app"], name)
            self.assertEqual(item["architectures"], ["amd64", "arm64"])
            self.assertIn("@sha256:", item["current_image"])

    def test_same_digest_skips_scanner(self):
        def scanner(*args):
            self.fail("unchanged digest must skip Trivy")
        report = audit.evaluate(sample(), resolver=lambda tag: (SHA, None), scanner=scanner)
        self.assertEqual(report["result"], "unchanged")

    def test_successful_reduction_on_both_arches(self):
        def scanner(image, arch):
            return {"critical": 0, "high": 1} if OTHER in image else {"critical": 1, "high": 9}
        report = audit.evaluate(sample(), resolver=lambda tag: (OTHER, None), scanner=scanner)
        self.assertEqual(report["result"], "lower_observed_cves")
        self.assertFalse(report["automatic_update_allowed"])

    def test_new_critical_blocks_even_if_high_drops(self):
        def scanner(image, arch):
            return {"critical": 2, "high": 0} if OTHER in image else {"critical": 0, "high": 60}
        report = audit.evaluate(sample(), resolver=lambda tag: (OTHER, None), scanner=scanner)
        self.assertEqual(report["result"], "not_better_on_all_architectures")

    def test_architecture_regression_blocks(self):
        def scanner(image, arch):
            old = {"critical": 1, "high": 8}
            new = {"critical": 0 if arch == "amd64" else 2, "high": 6}
            return new if OTHER in image else old
        report = audit.evaluate(sample(), resolver=lambda tag: (OTHER, None), scanner=scanner)
        self.assertEqual(report["result"], "not_better_on_all_architectures")

    def test_improvement_on_one_arch_and_unchanged_on_other_is_eligible(self):
        def scanner(image, arch):
            old = {"critical": 2, "high": 10}
            if OTHER in image and arch == "amd64":
                return {"critical": 1, "high": 7}
            return old
        report = audit.evaluate(sample(), resolver=lambda tag: (OTHER, None), scanner=scanner)
        self.assertEqual(report["result"], "lower_observed_cves")
        self.assertTrue(report["platforms"]["amd64"]["lower_cves"])
        self.assertFalse(report["platforms"]["arm64"]["lower_cves"])
        self.assertFalse(report["automatic_update_allowed"])

    def test_no_improvement_anywhere_does_not_qualify(self):
        report = audit.evaluate(sample(), resolver=lambda tag: (OTHER, None),
                                scanner=lambda image, arch: {"critical": 1, "high": 8})
        self.assertEqual(report["result"], "not_better_on_all_architectures")

    def test_high_regression_on_one_arch_blocks_despite_other_improvement(self):
        def scanner(image, arch):
            old = {"critical": 2, "high": 10}
            if OTHER not in image:
                return old
            return {"critical": 1, "high": 9} if arch == "amd64" else {"critical": 2, "high": 11}
        report = audit.evaluate(sample(), resolver=lambda tag: (OTHER, None), scanner=scanner)
        self.assertEqual(report["result"], "not_better_on_all_architectures")

    def test_registry_failure_is_inconclusive(self):
        report = audit.evaluate(sample(), resolver=lambda tag: (None, "429"))
        self.assertEqual(report["result"], "inconclusive")

    def test_invalid_scan_counts_are_inconclusive(self):
        report = audit.evaluate(sample(), resolver=lambda tag: (OTHER, None),
                                scanner=lambda *args: {"critical": None, "high": 0})
        self.assertEqual(report["result"], "inconclusive")

if __name__ == "__main__":
    unittest.main()
