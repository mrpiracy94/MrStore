"""Verify that the published-subtitle check also runs without third-party YAML.

The ZimaOS builder can change the active Python environment. This regression
test catches accidental imports of PyYAML from the independent JSON verifier
before the expensive 254-app build is started.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "curate_taglines.py"
SUMMARIES = ROOT / "data" / "taglines-pt.json"
PREFIX = "io.github.mrpiracy94."


class PublishedSubtitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summaries = json.loads(SUMMARIES.read_text(encoding="utf-8"))

    def invoke(self, entries, approved=None):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "index.json"
            p.write_text(json.dumps({"apps": entries}, ensure_ascii=False), encoding="utf-8")
            args = [sys.executable, "-S", str(SCRIPT), "--verify-dist", str(p)]
            if approved is not None:
                allowlist = Path(folder) / "quarantine.json"
                allowlist.write_text(json.dumps({"approved_apps": approved}))
                args.extend(["--approved-json", str(allowlist)])
            return subprocess.run(
                args,
                capture_output=True, text=True, timeout=20, check=False,
                cwd=ROOT,
            )

    def test_all_254_cards_pass_without_pyyaml(self):
        entries = [
            {"id": PREFIX + app, "tagline": tagline}
            for app, tagline in self.summaries.items()
        ]
        result = self.invoke(entries)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("254", result.stdout)

    def test_quarantined_subset_passes_without_pyyaml(self):
        selected = list(self.summaries)[:3]
        entries = [
            {"id": PREFIX + app, "tagline": self.summaries[app]}
            for app in selected
        ]
        result = self.invoke(entries, approved=selected)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("3", result.stdout)

    def test_not_approved_app_is_rejected(self):
        selected = list(self.summaries)[:2]
        wrong = list(self.summaries)[2]
        entries = [
            {"id": PREFIX + app, "tagline": self.summaries[app]}
            for app in selected + [wrong]
        ]
        result = self.invoke(entries, approved=selected)
        self.assertNotEqual(result.returncode, 0)

    def test_wrong_subtitle_causes_publication_failure(self):
        entries = [
            {"id": PREFIX + app, "tagline": tagline}
            for app, tagline in self.summaries.items()
        ]
        entries[0]["tagline"] = "Texto incorreto"
        result = self.invoke(entries)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("subtitle", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
