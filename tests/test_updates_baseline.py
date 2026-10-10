"""Regression tests: incomplete registry scans never advance digest baseline."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import updates


class UpdateBaselineTests(unittest.TestCase):
    def run_monitor(self, failed):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            before = {"checked_at": "prior", "images": {"example/image:1": "sha256:" + "a" * 64}}
            snapshot = temp / "digests.json"
            snapshot.write_text(json.dumps(before) + "\n", encoding="utf-8")
            output = temp / "report.json"
            summary = temp / "summary.md"
            after = {"checked_at": "new", "images": {"example/image:1": "sha256:" + "b" * 64}}
            report = {
                "checked": 1, "resolved": 0 if failed else 1,
                "changed": [], "first_seen": [],
                "failed": [{"image": "example/image:1", "error": "registry timeout"}] if failed else [],
            }
            cli = ["updates.py", "--root", str(temp), "--snapshot", str(snapshot),
                   "--output", str(output), "--summary", str(summary)]
            with patch.object(updates, "apps", return_value=[]), \
                 patch.object(updates, "image_usage", return_value={"example/image:1": ["example"]}), \
                 patch.object(updates, "monitor", return_value=(after, report)), \
                 patch.object(sys, "argv", cli):
                code = updates.main()
            self.assertEqual(code, 2 if failed else 0)
            self.assertTrue(output.is_file())
            self.assertTrue(summary.is_file())
            self.assertEqual(len(json.loads(output.read_text())["failed"]), int(failed))
            actual = json.loads(snapshot.read_text(encoding="utf-8"))
            self.assertEqual(actual, before if failed else after)

    def test_failed_scan_does_not_mutate_previous_digest_baseline(self):
        self.run_monitor(True)

    def test_complete_scan_updates_digest_baseline(self):
        self.run_monitor(False)


if __name__ == "__main__":
    unittest.main()
