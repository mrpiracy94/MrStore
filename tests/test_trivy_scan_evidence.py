"""Trivy must report scan evidence, not merely a successful exit code."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cves import audit_exit_status, evaluate, scan


class TrivyEvidenceTests(unittest.TestCase):
    def scan_mock(self, payload):
        response = subprocess.CompletedProcess(["trivy"], 0, json.dumps(payload), "")
        with patch("cves.subprocess.run", return_value=response) as run:
            findings, error = scan("example/vendor:1")
        run.assert_called_once()
        return findings, error

    def test_empty_results_are_inconclusive_not_clean(self):
        findings, error = self.scan_mock({"Results": []})
        self.assertEqual(findings, [])
        self.assertIn("no scanned targets", error)

    def test_invalid_targets_or_vulnerability_payloads_are_inconclusive(self):
        invalid = [
            {"Results": [None]},
            {"Results": [{}]},
            {"Results": [{"Target": ""}]},
            {"Results": [{"Target": 123}]},
            {"Results": [{"Target": "os", "Vulnerabilities": {"BAD": "shape"}}]},
            {"Results": [{"Target": "os", "Vulnerabilities": [None]}]},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                findings, error = self.scan_mock(payload)
                self.assertEqual(findings, [])
                self.assertIn("Incomplete Trivy report", error)

    def test_explicit_target_with_empty_vuln_list_is_valid(self):
        for entry in (
            {"Target": "example/image:1 (alpine 3)", "Vulnerabilities": []},
            {"Target": "example/image:1 (alpine 3)", "Vulnerabilities": None},
            {"Target": "example/image:1 (alpine 3)"},
        ):
            with self.subTest(entry=entry):
                findings, error = self.scan_mock({"Results": [entry]})
                self.assertEqual((findings, error), ([], None))

    def test_real_high_finding_is_preserved(self):
        finding = {"Severity": "HIGH", "VulnerabilityID": "CVE-TEST-123",
                   "PkgName": "libexample", "InstalledVersion": "1",
                   "FixedVersion": "2"}
        findings, error = self.scan_mock({
            "Results": [{"Target": "base-layer", "Vulnerabilities": [finding]}]
        })
        self.assertIsNone(error)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "HIGH")

    def test_release_and_daily_scans_fail_on_missing_evidence(self):
        with patch("cves.subprocess.run", return_value=subprocess.CompletedProcess(
                ["trivy"], 0, '{"Results":[]}', "")):
            result = evaluate({"img": ["app/web"]}, ["img"])
        self.assertEqual(result["failures"], 1)
        self.assertEqual(audit_exit_status(result), 2)
        self.assertEqual(result["results"][0]["status"], "error")


if __name__ == "__main__":
    unittest.main()
