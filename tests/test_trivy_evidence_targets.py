"""Reject empty or malformed Trivy evidence; never certify an unscanned image."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from cves import scan, evaluate
from release_scan import audit_shard


class TrivyEvidenceTargetTests(unittest.TestCase):
    def scan_report(self, data):
        completed = subprocess.CompletedProcess(
            ["trivy"], 0, json.dumps(data), "")
        with patch("cves.subprocess.run", return_value=completed) as runner, \
             patch("cves.time.sleep") as sleeper:
            findings, error = scan("example.test/demo:1")
        runner.assert_called_once()
        sleeper.assert_not_called()
        return findings, error

    def test_empty_results_are_inconclusive_not_clean(self):
        findings, error = self.scan_report({"Results": []})
        self.assertEqual(findings, [])
        self.assertIn("no scan targets", error)

    def test_missing_results_are_inconclusive(self):
        findings, error = self.scan_report({"ArtifactName": "image"})
        self.assertEqual(findings, [])
        self.assertIn("missing Results", error)

    def test_malformed_targets_are_inconclusive(self):
        for results in ([None], [{}], [{"Target": ""}],
                        [{"Target": 123}], [{"Target": "   "}]):
            with self.subTest(results=results):
                findings, error = self.scan_report({"Results": results})
                self.assertEqual(findings, [])
                self.assertIn("invalid scan target", error)

    def test_valid_zero_cve_target_is_not_blocked(self):
        findings, error = self.scan_report({"Results": [
            {"Target": "example.test/demo:1 (alpine 3.21)",
             "Vulnerabilities": None}]})
        self.assertEqual(findings, [])
        self.assertIsNone(error)

    def test_valid_high_severity_is_retained(self):
        findings, error = self.scan_report({"Results": [
            {"Target": "image (alpine)", "Vulnerabilities": [
                {"Severity": "HIGH", "VulnerabilityID": "CVE-TEST-1",
                 "PkgName": "example", "InstalledVersion": "1",
                 "FixedVersion": "2"}]}]})
        self.assertIsNone(error)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "HIGH")

    def test_inconclusive_report_increments_failures(self):
        completed = subprocess.CompletedProcess(
            ["trivy"], 0, '{"Results": []}', "")
        with patch("cves.subprocess.run", return_value=completed):
            report = evaluate({"example.test/demo:1": ["demo"]},
                              ["example.test/demo:1"])
        self.assertEqual(report["failures"], 1)
        self.assertEqual(report["results"][0]["status"], "error")

    def test_release_quarantines_zero_target_scan(self):
        from catalog import App
        app = App("example", ROOT / "Apps" / "example" / "docker-compose.yml",
                  {"services": {"web": {"image": "example.test/demo:1"}},
                   "x-casaos": {"main": "web", "architectures": ["amd64"]}},
                  {"main": "web", "architectures": ["amd64"]})
        with patch("cves.subprocess.run", return_value=subprocess.CompletedProcess(
                ["trivy"], 0, '{"Results": []}', "")):
            report = audit_shard(
                [app], 0, 1,
                resolver=lambda image: (image + "@sha256:" + "a" * 64, None),
                scanner=scan)
        result = report["results"][0]
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["scans"]["amd64"]["status"], "error")
        self.assertIn("no scan targets", result["scans"]["amd64"]["error"])


if __name__ == "__main__":
    unittest.main()
