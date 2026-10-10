"""Registry HTTP 429 is transient, not an image scan result."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from cves import RETRYABLE, scan
from release_scan import resolve_digest


class RegistryBackoffTests(unittest.TestCase):
    def test_plain_http_429_is_retryable(self):
        for diagnostic in (
            "HTTP 429 Too Many Requests",
            "Request failed with status 429:",
            "429: pull rate limit reached",
        ):
            with self.subTest(diagnostic=diagnostic):
                self.assertTrue(RETRYABLE.search(diagnostic), diagnostic)

    def test_unavailable_manifest_is_not_retryable(self):
        self.assertFalse(RETRYABLE.search("MANIFEST_UNKNOWN: requested image not found"))

    def test_trivy_retries_literal_http_429_then_preserves_findings(self):
        blocked = subprocess.CompletedProcess(["trivy"], 1, "", "HTTP 429 Too Many Requests")
        clean_report = subprocess.CompletedProcess(
            ["trivy"], 0, json.dumps({"Results": [{"Target": "target", "Vulnerabilities": [
                {"Severity": "HIGH", "VulnerabilityID": "CVE-2026-EXAMPLE",
                 "PkgName": "sample", "InstalledVersion": "1", "FixedVersion": "2"}
            ]}]}), ""
        )
        with patch("cves.subprocess.run", side_effect=[blocked, clean_report]) as runner, \
             patch("cves.time.sleep") as sleeper:
            findings, error = scan("example/app:1")
        self.assertIsNone(error)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "HIGH")
        self.assertEqual(runner.call_count, 2)
        sleeper.assert_called_once_with(12)

    def test_crane_retries_plain_429_then_requires_exact_digest(self):
        responses = iter((
            subprocess.CompletedProcess(["crane"], 1, "", "HTTP 429 Too Many Requests"),
            subprocess.CompletedProcess(["crane"], 0, "sha256:" + "b" * 64, ""),
        ))
        with patch("release_scan.time.sleep") as sleeper:
            def caller(args, **kwargs):
                return next(responses)
            pinned, error = resolve_digest("example/app:1", runner=caller, sleeper=sleeper)
        self.assertIsNone(error)
        self.assertEqual(pinned, "example/app:1@sha256:" + "b" * 64)
        sleeper.assert_called_once_with(12)


if __name__ == "__main__":
    unittest.main()
