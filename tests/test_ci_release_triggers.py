"""Prevent monitoring/test-only changes from saturating eight image-release scans.

Fail-closed rule: any actual release change MUST still run all security shards.
"""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(filename):
    with (ROOT / ".github" / "workflows" / filename).open(encoding="utf-8") as source:
        # BaseLoader preserves literal "on" rather than interpreting YAML 1.1 booleans.
        return yaml.load(source, Loader=yaml.BaseLoader)


class PublisherTriggerTests(unittest.TestCase):
    def test_test_only_changes_validate_but_do_not_reaudit_all_images(self):
        pub = workflow("publish.yml")
        valid = workflow("validate.yml")
        self.assertNotIn("tests/**", pub["on"]["pull_request"]["paths"])
        self.assertIn("tests/**", valid["on"]["push"]["paths"])
        self.assertIn("pull_request", valid["on"])
        self.assertNotIn("paths", valid["on"]["pull_request"] or {})

    def test_all_image_and_security_release_changes_still_trigger_release_audit(self):
        pub = workflow("publish.yml")
        release_paths = [
            "Apps/**",
            "scripts/catalog.py",
            "scripts/cves.py",
            "scripts/release_scan.py",
            "scripts/release_catalog.py",
            "scripts/image_freshness.py",
            "scripts/validate.py",
            "scripts/verify_dist.py",
            "scripts/privilege_policy.py",
            "scripts/compose_preflight.py",
            ".github/workflows/publish.yml",
        ]
        for event in ("push", "pull_request"):
            for path in release_paths:
                with self.subTest(event=event, path=path):
                    self.assertIn(path, pub["on"][event]["paths"])

    def test_security_gate_and_no_pr_publishing_are_retained(self):
        pub = workflow("publish.yml")
        jobs = pub["jobs"]
        # PR #81 moved expensive scans to actual releases; keep that rule.
        # Trigger path matching on PRs only gates fast preflight checks.
        self.assertEqual(jobs["security_audit"]["if"],
                         "github.event_name != 'pull_request'")
        self.assertEqual(jobs["security_audit"]["needs"], "preflight")
        self.assertEqual(jobs["build"]["needs"], "security_audit")
        self.assertEqual(jobs["publish"]["needs"], "build")
        self.assertEqual(jobs["security_audit"]["strategy"]["matrix"]["shard"],
                         [str(i) for i in range(8)])
        self.assertIn("github.event_name != 'pull_request'",
                      jobs["publish"]["if"])
        self.assertEqual(pub["permissions"]["contents"], "read")


if __name__ == "__main__":
    unittest.main()
