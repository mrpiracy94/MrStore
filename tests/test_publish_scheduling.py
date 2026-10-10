"""Prevent 32 expensive Trivy shards on PRs without relaxing release security.

The ordinary Validate MrStore and privilege/migration gates still run for PRs.
Full digest-locked Trivy scanning is mandatory for push/dispatch publication.
"""
from pathlib import Path
import sys
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class PublishSchedulingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ".github" / "workflows" / "publish.yml"
        cls.workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        cls.source = path.read_text(encoding="utf-8")

    def test_prs_still_get_preflight_but_never_launch_full_scan(self):
        jobs = self.workflow["jobs"]
        self.assertIn("preflight", jobs)
        # GitHub Actions YAML 'on' is boolean True under PyYAML YAML 1.1.
        triggers = self.workflow.get("on", self.workflow.get(True, {}))
        self.assertIn("pull_request", triggers)
        self.assertIn("push", triggers)
        self.assertIn("workflow_dispatch", triggers)
        self.assertNotIn("if", jobs["preflight"])
        scan = jobs["security_audit"]
        self.assertEqual(scan["if"], "github.event_name != 'pull_request'")
        self.assertEqual(scan["needs"], ["preflight", "prepare_crane"])

    def test_release_remains_fail_closed_on_32_full_shards(self):
        jobs = self.workflow["jobs"]
        scan = jobs["security_audit"]
        self.assertEqual(scan["strategy"]["matrix"]["shard"], list(range(32)))
        self.assertFalse(scan["strategy"]["fail-fast"])
        self.assertEqual(jobs["build"]["needs"], "security_audit")
        self.assertEqual(jobs["publish"]["needs"], "build")
        self.assertIn("github.ref == 'refs/heads/main'", jobs["publish"]["if"])
        self.assertTrue(any(
            "scripts/release_scan.py" in step.get("run", "")
            for step in scan["steps"] if isinstance(step, dict)
        ))
        self.assertTrue(any(
            "scripts/release_catalog.py" in step.get("run", "")
            for step in jobs["build"]["steps"] if isinstance(step, dict)
        ))
        self.assertTrue(any(
            step.get("name") == "Fetch 32 mandatory security evidence reports"
            for step in jobs["build"]["steps"]
        ))
        self.assertFalse(any(step.get("continue-on-error")
                             for step in scan["steps"] if isinstance(step, dict)))
        self.assertIn("if: success()", self.source)

    def test_validation_remains_unconditional_on_pr(self):
        validate = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
        )
        triggers = validate.get("on", validate.get(True, {}))
        self.assertIn("pull_request", triggers)
        actions = " ".join(str(s.get("run", "")) for s in
                           validate["jobs"]["validate"]["steps"])
        for script in ("scripts/validate.py", "scripts/compatibility.py",
                       "scripts/compose_preflight.py", "scripts/privilege_policy.py"):
            self.assertIn(script, actions)


if __name__ == "__main__":
    unittest.main()
