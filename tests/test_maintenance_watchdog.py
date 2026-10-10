"""Offline regression tests for the scheduled maintenance watchdog."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import maintenance_watchdog as mw


NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)


def run(hours=1, conclusion="success", status="completed"):
    return {
        "created_at": (NOW - timedelta(hours=hours)).isoformat(),
        "status": status, "conclusion": conclusion,
        "html_url": "https://github.com/mrpiracy94/MrStore/actions/runs/123",
    }


class WatchdogTests(unittest.TestCase):
    def test_successful_recent_run_is_healthy(self):
        status, problem = mw.evaluate_run(
            "cve-scan.yml", [run()], NOW, 60, "mrpiracy94/MrStore")
        self.assertIsNone(problem)
        self.assertIn("OK", status)

    def test_failed_scan_is_not_reported_as_healthy(self):
        _, problem = mw.evaluate_run(
            "cve-scan.yml", [run(conclusion="failure")],
            NOW, 60, "mrpiracy94/MrStore")
        self.assertEqual(problem["id"], "failed:cve-scan.yml:failure")
        self.assertIn("logs", problem["message"])

    def test_stale_schedule_is_flagged_even_without_new_commits(self):
        _, problem = mw.evaluate_run(
            "image-freshness.yml", [run(hours=230)],
            NOW, 216, "mrpiracy94/MrStore")
        self.assertEqual(problem["id"], "stale:image-freshness.yml")

    def test_no_schedule_is_not_claimed_as_passed(self):
        _, problem = mw.evaluate_run(
            "discover-apps.yml", [], NOW, 960, "mrpiracy94/MrStore")
        self.assertEqual(problem["id"], "missing:discover-apps.yml")

    def test_recent_workflow_without_first_schedule_is_not_prematurely_failed(self):
        created = (NOW - timedelta(hours=4)).isoformat()
        status, problem = mw.evaluate_run(
            "discover-apps.yml", [], NOW, 960, "mrpiracy94/MrStore", created)
        self.assertIsNone(problem)
        self.assertIn("A aguardar primeira execução", status)
        self.assertNotIn("OK", status)

    def test_bootstrap_grace_expires_for_missing_schedule(self):
        created = (NOW - timedelta(hours=961)).isoformat()
        _, problem = mw.evaluate_run(
            "discover-apps.yml", [], NOW, 960, "mrpiracy94/MrStore", created)
        self.assertEqual(problem["id"], "missing:discover-apps.yml")

    def test_failed_run_remains_failed_even_if_workflow_was_created_today(self):
        created = (NOW - timedelta(hours=2)).isoformat()
        _, problem = mw.evaluate_run(
            "cve-scan.yml", [run(conclusion="failure")], NOW,
            60, "mrpiracy94/MrStore", created)
        self.assertEqual(problem["id"], "failed:cve-scan.yml:failure")

    def test_future_workflow_creation_date_is_not_treated_as_grace(self):
        created = (NOW + timedelta(hours=1)).isoformat()
        _, problem = mw.evaluate_run(
            "cve-scan.yml", [], NOW, 60, "mrpiracy94/MrStore", created)
        self.assertEqual(problem["id"], "missing:cve-scan.yml")

    def test_malformed_workflow_creation_date_is_not_a_grace_pass(self):
        for created in ("not-a-date", "2026-99-99", ""):
            with self.subTest(created=created):
                _, problem = mw.evaluate_run(
                    "cve-scan.yml", [], NOW, 60, "mrpiracy94/MrStore",
                    created)
                self.assertEqual(problem["id"], "missing:cve-scan.yml")

    def test_disabled_workflow_is_flagged_even_inside_bootstrap_grace(self):
        with patch.dict(mw.WORKFLOWS, {"cve-scan.yml": 60}, clear=True), \\
             patch.object(mw, "api", return_value={
                 "state": "disabled_manually",
                 "created_at": (NOW - timedelta(hours=1)).isoformat()
             }) as api, \\
             patch.object(mw, "api_pages", return_value=[]):
            problems, notes, outcomes = mw.github_review("mrpiracy94/MrStore", NOW)
        self.assertEqual([item["id"] for item in problems],
                         ["inactive:cve-scan.yml"])
        self.assertIn("inativo", outcomes["workflows"]["cve-scan.yml"])
        self.assertTrue(any("⚠️" in note for note in notes))
        api.assert_called_once()  # Disabled schedule should not be marked healthy.

    def test_active_recent_run_is_not_a_failure(self):
        _, problem = mw.evaluate_run(
            "cve-scan.yml", [run(hours=1, status="in_progress", conclusion=None)],
            NOW, 60, "mrpiracy94/MrStore")
        self.assertIsNone(problem)

    def test_overdue_active_run_is_flagged(self):
        _, problem = mw.evaluate_run(
            "cve-scan.yml", [run(hours=7, status="in_progress", conclusion=None)],
            NOW, 60, "mrpiracy94/MrStore")
        self.assertEqual(problem["id"], "stuck:cve-scan.yml")

    def test_stale_prs_are_not_merged_or_closed(self):
        prs = [
            {"number": 2, "updated_at": (NOW - timedelta(days=20)).isoformat(),
             "draft": True, "html_url": "https://github.com/example/pr/2"},
            {"number": 3, "updated_at": (NOW - timedelta(days=2)).isoformat()},
        ]
        findings = mw.stale_prs(prs, NOW, "mrpiracy94/MrStore")
        self.assertEqual([i["id"] for i in findings], ["stale-pr:2"])

    def test_fingerprint_dedupes_without_suppressing_findings(self):
        a = mw.finding("local", "manifest", "some error")
        b = mw.finding("workflow", "scan", "some error")
        self.assertEqual(mw.fingerprint([a, b]), mw.fingerprint([b, a]))
        self.assertNotEqual(mw.fingerprint([a]), mw.fingerprint([]))

    def test_existing_identical_issue_is_not_updated_every_day(self):
        problems = [mw.finding("local", "manifest", "not green")]
        with patch.object(mw, "api_pages", return_value=[{
            "number": 99, "title": mw.TITLE, "state": "open",
            "body": f"<!-- maintenance-watchdog-signature:{mw.fingerprint(problems)} -->"
        }]), patch.object(mw, "api") as github:
            result = mw.sync_issue("mrpiracy94/MrStore", problems, "body")
            self.assertIn("Unchanged", result)
            github.assert_not_called()

    def test_recovery_closes_only_existing_watchdog_issue(self):
        with patch.object(mw, "api_pages", return_value=[{
            "number": 99, "title": mw.TITLE, "state": "open", "body": ""
        }]), patch.object(mw, "api") as github:
            result = mw.sync_issue("mrpiracy94/MrStore", [], "green")
            self.assertIn("Closed", result)
            self.assertEqual(github.call_args.args[1], "PATCH")
            self.assertEqual(github.call_args.args[2]["state"], "closed")

    def test_duplicate_tracker_issues_fail_safely(self):
        with patch.object(mw, "api_pages", return_value=[
            {"number": 1, "title": mw.TITLE},
            {"number": 2, "title": mw.TITLE}
        ]):
            with self.assertRaisesRegex(RuntimeError, "multiple"):
                mw.sync_issue("mrpiracy94/MrStore", [], "")


if __name__ == "__main__":
    unittest.main()
