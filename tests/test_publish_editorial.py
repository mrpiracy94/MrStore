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

    def test_editorial_workflow_never_overwrites_audited_gh_pages(self):
        text = (ROOT / ".github/workflows/rollout-233.yml").read_text()
        self.assertIn("mrstore-editorial-preview-254", text)
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertNotIn("peaceiris/actions-gh-pages", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("raw.githubusercontent.com/mrpiracy94/MrStore/gh-pages", text)


if __name__ == "__main__":
    unittest.main()
