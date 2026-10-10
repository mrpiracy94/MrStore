import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_patched_go_release import check


class GoPatchSecurityGateTests(unittest.TestCase):
    def good(self):
        return {"Results": [
            {"Target": "alpine:3.24 (alpine 3.24)", "Vulnerabilities": []},
            {"Target": "/app/gitea/gitea", "Vulnerabilities": []},
        ]}

    def test_verified_empty_findings_pass(self):
        self.assertEqual(check(self.good()), {"HIGH": 0, "CRITICAL": 0})

    def test_missing_and_empty_results_fail_closed(self):
        for report in ({}, {"Results": []}, {"Results": None}):
            with self.subTest(report=report), self.assertRaises(ValueError):
                check(report)

    def test_high_and_critical_findings_block(self):
        for severity in ("HIGH", "CRITICAL"):
            report = self.good()
            report["Results"][1]["Vulnerabilities"] = [
                {"VulnerabilityID": "CVE-2026-78669", "Severity": severity}]
            with self.subTest(severity=severity), self.assertRaisesRegex(ValueError, "Blocking release"):
                check(report)

    def test_inconclusive_reports_fail(self):
        for bad in (
            {"Results": [{"Target": "", "Vulnerabilities": []}]},
            {"Results": [{"Target": "some", "Vulnerabilities": "invalid"}]},
            {"Results": [{"Target": "some", "Vulnerabilities": [{}]}]},
            {"Results": [{"Target": "some", "Vulnerabilities": [
                {"VulnerabilityID": "CVE-123", "Severity": "BROKEN"}]}]},
        ):
            with self.subTest(report=bad), self.assertRaises(ValueError):
                check(bad)


if __name__ == "__main__":
    unittest.main()
