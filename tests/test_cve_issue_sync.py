"""Offline tests for safe CVE issue consolidation (no GitHub requests)."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sync_cve_issues import sync


class IssueSyncTests(unittest.TestCase):
    def run_sync(self, issues, critical=1, high=3, failures=0, coverage=None):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "cves.json"
            summary_path = Path(tmp) / "cves.md"
            report_path.write_text(json.dumps({
                "shard": 1, "critical": critical, "high": high, "failures": failures,
                "coverage": coverage,
            }), encoding="utf-8")
            summary_path.write_text("# Full CVE evidence\n", encoding="utf-8")
            calls = []

            def runner(args, **kwargs):
                calls.append(args)
                if args[:3] == ["gh", "issue", "list"]:
                    return subprocess.CompletedProcess(args, 0, json.dumps(issues), "")
                return subprocess.CompletedProcess(args, 0, "", "")

            result = sync(report_path, summary_path, runner=runner)
            return result, calls

    def test_duplicate_legacy_issue_is_consolidated_after_update(self):
        issues = [
            {"number": 16, "title": "MrStore CVE CRITICAL — shard 1", "state": "OPEN"},
            {"number": 15, "title": "MrStore CVE HIGH/CRITICAL — shard 1", "state": "OPEN"},
            {"number": 14, "title": "MrStore CVE HIGH/CRITICAL — shard 2", "state": "OPEN"},
        ]
        result, calls = self.run_sync(issues)
        self.assertEqual(result, {"action": "updated", "duplicates_closed": 1})
        self.assertEqual(calls[1][:4], ["gh", "issue", "edit", "15"])
        self.assertEqual(calls[2][:4], ["gh", "issue", "comment", "16"])
        self.assertEqual(calls[3], ["gh", "issue", "close", "16"])
        self.assertFalse(any(x[:3] == ["gh", "issue", "close"] and x[-1] == "15" for x in calls))

    def test_incomplete_clean_looking_scan_keeps_existing_warnings(self):
        issues = [
            {"number": 15, "title": "MrStore CVE HIGH/CRITICAL — shard 1", "state": "OPEN"},
            {"number": 16, "title": "MrStore CVE CRITICAL — shard 1", "state": "OPEN"},
        ]
        result, calls = self.run_sync(issues, critical=0, high=0, failures=2)
        self.assertEqual(result["action"], "scan_incomplete")
        self.assertEqual(len(calls), 1)

    def test_clean_complete_scan_closes_both_with_history_preserved(self):
        issues = [
            {"number": 15, "title": "MrStore CVE HIGH/CRITICAL — shard 1", "state": "OPEN"},
            {"number": 16, "title": "MrStore CVE CRITICAL — shard 1", "state": "OPEN"},
        ]
        result, calls = self.run_sync(issues, critical=0, high=0, coverage={
            "amd64": {"complete": True, "scanned": 10, "expected": 10},
            "arm64": {"complete": True, "scanned": 10, "expected": 10},
        })
        self.assertEqual(result, {"action": "closed", "duplicates_closed": 1})
        self.assertEqual([x[-1] for x in calls if x[:3] == ["gh", "issue", "close"]], ["15", "16"])

    def test_zero_findings_without_architecture_coverage_stays_open(self):
        issues = [{"number": 15, "title": "MrStore CVE HIGH/CRITICAL — shard 1", "state": "OPEN"}]
        result, calls = self.run_sync(issues, critical=0, high=0)
        self.assertEqual(result["action"], "scan_incomplete")
        self.assertFalse(any(x[:3] == ["gh", "issue", "close"] for x in calls))

    def test_reopens_a_closed_canonical_when_findings_return(self):
        issues = [
            {"number": 15, "title": "MrStore CVE HIGH/CRITICAL — shard 1", "state": "CLOSED"}
        ]
        result, calls = self.run_sync(issues)
        self.assertEqual(result["action"], "updated")
        self.assertEqual(calls[1], ["gh", "issue", "reopen", "15"])
        self.assertEqual(calls[2][:4], ["gh", "issue", "edit", "15"])

    def test_32_shard_clean_issue_is_closed_when_image_evidence_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "cves.json"
            summary = Path(tmp) / "cves.md"
            report.write_text(json.dumps({
                "shard": 31, "shards": 32, "critical": 0, "high": 0,
                "failures": 0,
                "coverage": {
                    "amd64": {"complete": True, "expected": 8, "scanned": 8},
                    "arm64": {"complete": True, "expected": 7, "scanned": 7},
                },
            }))
            summary.write_text("# Sem alertas no grupo 31\\n")
            calls = []
            title = "MrStore CVE HIGH/CRITICAL — 32-shard 31"

            def runner(args, **kwargs):
                calls.append(args)
                if args[:3] == ["gh", "issue", "list"]:
                    return subprocess.CompletedProcess(args, 0, json.dumps([
                        {"number": 51, "title": title, "state": "OPEN"},
                        {"number": 15, "title":
                         "MrStore CVE HIGH/CRITICAL — shard 7",
                         "state": "OPEN"},
                    ]), "")
                return subprocess.CompletedProcess(args, 0, "", "")

            outcome = sync(report, summary, runner=runner)
            self.assertEqual(outcome["action"], "closed")
            self.assertTrue(any(cmd[:3] == ["gh", "issue", "close"]
                                and cmd[-1] == "51" for cmd in calls))
            self.assertFalse(any(cmd[:3] == ["gh", "issue", "close"]
                                 and cmd[-1] == "15" for cmd in calls))

    def test_32_shard_single_architecture_results_do_not_close_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "cves.json"
            summary = Path(tmp) / "cves.md"
            report.write_text(json.dumps({
                "shard": 31, "shards": 32, "critical": 0, "high": 0,
                "failures": 0,
                "coverage": {"images": {"complete": True,
                    "expected": 8, "scanned": 8}},
            }))
            summary.write_text("# No findings on default runner architecture\\n")
            calls = []

            def runner(args, **kwargs):
                calls.append(args)
                if args[:3] == ["gh", "issue", "list"]:
                    return subprocess.CompletedProcess(args, 0, json.dumps([
                        {"number": 51, "title":
                         "MrStore CVE HIGH/CRITICAL — 32-shard 31",
                         "state": "OPEN"},
                    ]), "")
                return subprocess.CompletedProcess(args, 0, "", "")

            outcome = sync(report, summary, runner=runner)
            self.assertEqual(outcome["action"], "scan_incomplete")
            self.assertFalse(any(cmd[:3] == ["gh", "issue", "close"]
                                 for cmd in calls))

    def test_32_shard_incomplete_evidence_keeps_cve_issue_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "cves.json"
            summary = Path(tmp) / "cves.md"
            report.write_text(json.dumps({
                "shard": 0, "shards": 32, "critical": 0, "high": 0,
                "failures": 1,
                "coverage": {"images": {"complete": False,
                    "expected": 8, "scanned": 7}},
            }))
            summary.write_text("# Inconclusivo\\n")
            calls = []

            def runner(args, **kwargs):
                calls.append(args)
                if args[:3] == ["gh", "issue", "list"]:
                    return subprocess.CompletedProcess(args, 0, json.dumps([
                        {"number": 52, "title":
                         "MrStore CVE HIGH/CRITICAL — 32-shard 0",
                         "state": "OPEN"},
                    ]), "")
                return subprocess.CompletedProcess(args, 0, "", "")
            outcome = sync(report, summary, runner=runner)
            self.assertEqual(outcome["action"], "scan_incomplete")
            self.assertEqual(len(calls), 1)

    def test_workflow_keeps_failing_when_vulnerabilities_remain(self):
        workflow = (ROOT / ".github/workflows/cve-scan.yml").read_text(encoding="utf-8")
        self.assertIn("run: python scripts/sync_cve_issues.py", workflow)
        self.assertIn("if: steps.scan.outcome == 'failure'", workflow)
        self.assertIn("exit 1", workflow)


if __name__ == "__main__":
    unittest.main()
