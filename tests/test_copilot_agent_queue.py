"""Offline routing and safety tests for the Copilot issue queue."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from copilot_agent_queue import classify, queue, render  # noqa: E402


def issue(number, title, **extra):
    return {"number": number, "state": "open", "title": title,
            "labels": [], "assignees": [], **extra}


class RoutingTests(unittest.TestCase):
    def test_specialists_and_priorities(self):
        candidates = [
            issue(8, "MrStore image updates — 2026-10-09"),
            issue(22, "MrStore CVE HIGH/CRITICAL — shard 6"),
            issue(42, "Rebrand homepage website"),
            issue(95, "MrStore automated maintenance watchdog"),
        ]
        ready, blocked = queue(candidates, [])
        self.assertEqual([(v["issue"], v["agent"]) for v in ready], [
            (22, "security-cve"), (8, "dependency-updates"),
            (42, "storefront-ui"), (95, "operations-ci"),
        ])
        self.assertEqual(blocked, [])

    def test_references_in_open_pr_block_duplicate_work(self):
        r, b = queue([issue(95, "Maintenance watchdog broken")], [
            {"state": "open", "title": "fix watchdog", "body": "Relates to #95"}])
        self.assertEqual(r, [])
        self.assertEqual(b[0]["reason"], "linked_open_pr")

    def test_human_only_runtime_and_migration(self):
        for title in ("Piloto C3 — instalações reais no NAS",
                      "Immich migração postgres com backup e rollback",
                      "Certificação ZimaOS em dispositivo"):
            self.assertIsNone(classify(issue(1, title)))

    def test_hold_and_already_delegated(self):
        for labels in ([{"name": "agent:hold"}], [{"name": "agent:delegated"}]):
            q, b = queue([issue(5, "CVE security alerts", labels=labels)], [])
            self.assertFalse(q)
            self.assertEqual(b[0]["reason"], "held_or_delegated")

    def test_bot_and_human_assignments_do_not_get_reassigned(self):
        for assignees in ([{"login": "copilot-swe-agent[bot]"}],
                          [{"login": "mrpiracy94"}]):
            q, b = queue([issue(5, "CVE security alerts", assignees=assignees)], [])
            self.assertEqual(q, [])
            self.assertEqual(len(b), 1)

    def test_issues_endpoint_prs_not_mistaken_for_issues(self):
        ready, blocked = queue([issue(11, "CVE security", pull_request={"url": "pr"})], [])
        self.assertEqual((ready, blocked), ([], []))

    def test_unknown_titles_not_automatically_assigned(self):
        self.assertEqual(queue([issue(13, "A question about the logo")], []), ([], []))

    def test_render_reports_real_assignments_only(self):
        output = render({"mode": "audit", "ready": [], "blocked": [],
                         "assigned": [], "note": "No token"})
        self.assertIn("atribuídos nesta execução: **0**", output)
        self.assertNotIn("✅ #", output)


if __name__ == "__main__":
    unittest.main()
