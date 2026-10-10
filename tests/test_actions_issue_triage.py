"""Offline regression tests for read-only GitHub Actions issue triage."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import actions_issue_triage as triage


def issue(number, title, state="open"):
    return {"number": number, "title": title, "state": state}


def workflow_run(run_id=123, status="completed", conclusion="failure"):
    return {"id": run_id, "status": status, "conclusion": conclusion,
            "created_at": "2026-10-10T10:00:00Z",
            "html_url": "https://github.com/mrpiracy94/MrStore/actions/runs/123"}


class TriageTests(unittest.TestCase):
    REPO = "mrpiracy94/MrStore"

    def test_known_issue_categories_and_cve_shards(self):
        expected = {94: "publication", 95: "maintenance", 8: "updates",
                    58: "migrations", 53: "security", 45: "compatibility",
                    3: "dependencies", 19: "cve"}
        for number, category in expected.items():
            with self.subTest(number=number):
                self.assertEqual(triage.classify(issue(number, "Something")), category)

    def test_unknown_issue_classified_by_title(self):
        self.assertEqual(triage.classify(issue(501, "New CVE affects Redis")), "cve")
        self.assertEqual(triage.classify(issue(502, "Immich database migration")), "migrations")
        self.assertEqual(triage.classify(issue(503, "Unexpected socket privileges")), "security")

    def test_no_pr_in_issue_list_and_no_false_cve_closure(self):
        issues = [issue(19, "MrStore CVE HIGH/CRITICAL — shard 5"),
                  issue(94, "MrStore public catalog availability incident"),
                  dict(issue(120, "PR #120"), pull_request={"url": "https://example"})]
        runs = {"cve-scan.yml": [workflow_run(conclusion="success")],
                "retry-inconclusive-cves.yml": []}
        report = triage.build_report(
            self.REPO, issues, [], runs, focus="cve",
            generated_at="2026-10-10T10:00:00Z")
        self.assertEqual([i["number"] for i in report["selected_issues"]], [19])
        self.assertEqual(report["selected_issues"][0]["shard"], 5)
        self.assertEqual(report["open_issues_observed"], 2)
        self.assertEqual(report["workflow_runs"][0]["state"], "concluido")
        self.assertIn("não", triage.render_markdown(report).lower())
        self.assertFalse(any("fixed" in str(item).lower()
                             for item in report["selected_issues"]))

    def test_failed_steps_are_bound_and_do_not_include_logs(self):
        runs = [workflow_run()]
        jobs = [{
            "name": "preflight", "conclusion": "failure",
            "html_url": "https://github.com/job/1",
            "steps": [{"name": "Checkout", "conclusion": "success"},
                      {"name": "Validate manifests", "conclusion": "failure"}]
        }, {"name": "other", "conclusion": "success",
            "steps": [{"name": "SecretToken", "conclusion": "failure"}]}]
        record = triage.run_record("validate.yml", runs, jobs)
        self.assertEqual(record["state"], "falhou")
        self.assertEqual(record["failed_jobs"][0]["steps"], ["Validate manifests"])
        self.assertNotIn("SecretToken", str(record))

    def test_pending_is_never_success(self):
        record = triage.run_record(
            "publish.yml", [workflow_run(status="queued", conclusion=None)])
        self.assertEqual(record["state"], "a_decorrer")
        self.assertEqual(triage.run_record("publish.yml", [])["state"], "sem_execucao")

    def test_unknown_selected_issue_is_an_error_not_empty_success(self):
        with self.assertRaisesRegex(ValueError, "not open"):
            triage.build_report(self.REPO, [issue(94, "Public incident", "closed")],
                                [], {}, focus="all", issue_number=94)

    def test_wrong_focus_for_selected_issue_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not open"):
            triage.build_report(self.REPO, [issue(94, "Public incident")],
                                [], {}, focus="cve", issue_number=94)

    def test_malicious_title_has_no_markdown_table_or_new_heading(self):
        text = triage.clean("bad | ] link [\n# heading", 150)
        self.assertNotIn("|", text)
        self.assertNotIn("\n", text)
        self.assertNotIn("[", text)

    def test_pagination_refuses_partial_issue_inventory(self):
        with patch.object(triage, "get_json", return_value=[{"number": 5}] * 100):
            with self.assertRaisesRegex(ValueError, "limit"):
                triage.list_pages(self.REPO, f"/repos/{self.REPO}/issues?state=open",
                                  "token", max_pages=1)

    def test_only_metadata_and_read_only_api_endpoints(self):
        with self.assertRaisesRegex(ValueError, "Only same-repository"):
            triage.get_json(self.REPO, "/repos/other/project/issues", "dummy")

    def test_generate_report_has_actionable_issue_and_links(self):
        data = triage.build_report(
            self.REPO, [issue(94, "Public catalog broken")],
            [{"number": 115, "state": "open"}],
            {"catalog-uptime.yml": [workflow_run()],
             "publish.yml": []},
            focus="publication", generated_at="2026-10-10T10:00:00Z")
        md = triage.render_markdown(data)
        self.assertIn("issues/94", md)
        self.assertIn("catalog-uptime.yml", md)
        self.assertIn("release-status.json", md)
        self.assertEqual(data["open_prs_observed"], 1)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            output.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(json.loads(output.read_text())["focus"], "publication")

    def test_collect_only_reads_relevant_workflows_and_failed_jobs(self):
        paths = []
        def fake_get(_repo, path, _token):
            paths.append(path)
            if "catalog-uptime.yml" in path:
                return {"workflow_runs": [workflow_run()]}
            if "publish.yml" in path:
                return {"workflow_runs": []}
            if "/actions/runs/123/jobs" in path:
                return {"jobs": [{"name": "probe", "conclusion": "failure",
                                  "steps": [{"name": "HTTP 404", "conclusion": "failure"}]}]}
            raise AssertionError("Unexpected endpoint " + path)
        with patch.object(triage, "list_pages", side_effect=[
                [issue(94, "MrStore public catalog availability incident")],
                [{"state": "open"}]]):
            data = triage.collect(self.REPO, "dummy", "publication", 94, get=fake_get)
        self.assertEqual(data["selected_issues"][0]["number"], 94)
        self.assertEqual(data["workflow_runs"][0]["failed_jobs"][0]["steps"],
                         ["HTTP 404"])
        self.assertEqual(len(paths), 3)
        self.assertFalse(any("/logs" in x for x in paths))


if __name__ == "__main__":
    unittest.main()
