"""Regression tests for safe editorial staging and publication boundaries."""
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import publish_editorial  # noqa: E402


class EditorialSafetyTests(unittest.TestCase):
    def test_missing_subtitle_fails_before_creating_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "release-source"
            report = Path(tmp) / "out" / "release-selection.json"
            args = [
                "publish_editorial.py", "--stage", str(stage),
                "--report", str(report),
            ]
            with (
                patch.object(sys, "argv", args),
                patch.object(publish_editorial, "apps", return_value=[
                    SimpleNamespace(folder="filebrowser")
                ]),
                patch.object(publish_editorial, "load_featured",
                             return_value=("filebrowser",)),
                patch.object(publish_editorial, "load_summaries",
                             return_value={}),
            ):
                with self.assertRaisesRegex(SystemExit, "filebrowser"):
                    publish_editorial.main()
            self.assertFalse(stage.exists(), "Partial stage must not exist")
            self.assertFalse(report.exists(), "No release report on failure")

    def test_full_editorial_workflow_publishes_all_sources_without_security_claims(self):
        text = (ROOT / ".github/workflows/rollout-233.yml").read_text()
        self.assertIn("p.parent.name for p in Path('Apps').glob('*/docker-compose.yml')", text)
        self.assertIn("mrstore-complete-editorial-catalog", text)
        self.assertIn("peaceiris/actions-gh-pages@v4", text)
        self.assertIn("certification'] != 'not_assessed'", text)
        self.assertIn("set(ids) != source", text)
        self.assertNotIn("scripts/release_scan.py", text)

    def test_audited_release_cannot_replace_all_apps_with_a_subset(self):
        text = (ROOT / ".github/workflows/publish.yml").read_text()
        self.assertIn("Refusing to replace full MrStore catalog with a filtered release", text)
        self.assertIn("set(ids) != source", text)



if __name__ == "__main__":
    unittest.main()
