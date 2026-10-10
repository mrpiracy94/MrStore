"""Stop green pull-request checks hiding skipped release-audit/build stages.

The PR build is a real dry-run of security scanning and catalog generation,
NOT real-device certification, and must never deploy to gh-pages.
"""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ReleaseWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
        cls.workflow = yaml.load(cls.text, Loader=yaml.BaseLoader)

    def test_pr_triggers_full_scan_not_preflight_only(self):
        trigger = self.workflow["on"]
        self.assertIn("pull_request", trigger)
        self.assertIn("workflow_dispatch", trigger)
        jobs = self.workflow["jobs"]
        self.assertIn("preflight", jobs)
        self.assertIn("security_audit", jobs)
        self.assertIn("build", jobs)
        self.assertNotIn("if", jobs["security_audit"])
        self.assertNotIn("if", jobs["build"])
        self.assertEqual(jobs["security_audit"]["needs"], "preflight")
        self.assertEqual(jobs["build"]["needs"], "security_audit")
        self.assertEqual(jobs["security_audit"]["strategy"]["matrix"]["shard"],
                         list(map(str, range(8))))
        self.assertEqual(jobs["security_audit"]["strategy"]["max-parallel"], "8")

    def test_green_build_requires_real_catalog_artifacts(self):
        build_steps = self.workflow["jobs"]["build"]["steps"]
        checks = [step for step in build_steps
                  if "REQUIRE real audited ZimaOS and Universal output" in step.get("name", "")]
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].get("if"), "github.event_name == 'pull_request'")
        script = checks[0]["run"]
        for artifact in ("out/release-selection.json", "out/release-compose.json",
                         "dist/store.json", "dist/index.json",
                         "dist/universal/catalog.json", "dist/universal/support-report.json"):
            self.assertIn(artifact, script)
        self.assertIn('len(support["systems"]) == 11', script)
        self.assertIn("total > 0", script)

    def test_pull_requests_never_publish_but_main_can(self):
        publication = self.workflow["jobs"]["publish"]
        self.assertIn("github.ref == 'refs/heads/main'", publication["if"])
        self.assertIn("github.event_name != 'pull_request'", publication["if"])
        self.assertEqual(publication["needs"], "build")
        self.assertIn("gh-pages", self.text)


if __name__ == "__main__":
    unittest.main()
