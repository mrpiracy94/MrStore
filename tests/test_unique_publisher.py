"""Only the complete 254-app publisher may automatically modify gh-pages."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1] / ".github/workflows"


def workflow(name):
    return yaml.load((ROOT / name).read_text(encoding="utf-8"),
                     Loader=yaml.BaseLoader)


class PublicationOwnershipTests(unittest.TestCase):
    def test_full_catalog_updates_on_main_web_and_app_changes(self):
        doc = workflow("rollout-233.yml")
        self.assertIn("web/**", doc["on"]["push"]["paths"])
        self.assertIn("Apps/**", doc["on"]["push"]["paths"])
        self.assertIn(".github/workflows/rollout-233.yml", doc["on"]["push"]["paths"])
        self.assertIn("Publish full editorial catalog", str(doc["jobs"]["publish"]["steps"]))

    def test_website_only_publishes_on_explicit_manual_dispatch(self):
        doc = workflow("publish-storefront.yml")
        self.assertIn("push", doc["on"])
        self.assertIn("pull_request", doc["on"])
        self.assertIn("workflow_dispatch", doc["on"])
        self.assertIn("github.event_name == 'workflow_dispatch'",
                      doc["jobs"]["publish_site"]["if"])
        self.assertEqual(doc["jobs"]["verify_ui"]["if"],
                         "github.event_name != 'workflow_dispatch'")

    def test_historical_mutating_jobs_cannot_run_on_main_push(self):
        for name in ("restore-public-233.yml", "withdraw-retired-steamos.yml"):
            with self.subTest(workflow=name):
                doc = workflow(name)
                self.assertNotIn("push", doc["on"])
                self.assertNotIn("pull_request", doc["on"])
                self.assertIn("workflow_dispatch", doc["on"])


if __name__ == "__main__":
    unittest.main()
