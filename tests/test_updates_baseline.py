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
            # A baseline aprovada é imutável, mesmo após consulta completa.
            self.assertEqual(actual, before)
            live = temp / "updates-live-digests.json"
            self.assertEqual(live.exists(), not failed)
            if not failed:
                self.assertEqual(json.loads(live.read_text(encoding="utf-8")), after)

    def test_failed_scan_does_not_mutate_previous_digest_baseline(self):
        self.run_monitor(True)

    def test_complete_scan_updates_digest_baseline(self):
        self.run_monitor(False)


class PinnedSourceUpdateTests(unittest.TestCase):
    OLD = "sha256:" + "a" * 64
    NEW = "sha256:" + "b" * 64

    def test_pinned_images_resolve_tags_not_old_digests(self):
        pinned = "example/image:latest@" + self.OLD
        calls = []
        def resolver(tag):
            calls.append(tag)
            return self.NEW, None
        _, report = updates.monitor(
            {pinned: ["example/service"]},
            {"images": {"example/image:latest": self.OLD}}, resolver=resolver)
        self.assertEqual(calls, ["example/image:latest"])
        self.assertEqual(report["checked"], 1)
        self.assertEqual(report["resolved"], 1)
        self.assertEqual(len(report["changed"]), 1)
        self.assertEqual(report["changed"][0]["old"], self.OLD)
        self.assertEqual(report["changed"][0]["new"], self.NEW)
        self.assertEqual(report["changed"][0]["source_image"], pinned)

    def test_missing_reviewed_baseline_blocks_lookup(self):
        pinned = "example/image:latest@" + self.OLD
        calls = []
        _, report = updates.monitor(
            {pinned: ["x"]}, {"images": {}},
            resolver=lambda tag: (calls.append(tag), None))
        self.assertEqual(calls, [])
        self.assertEqual(report["resolved"], 0)
        self.assertIn("baseline", report["failed"][0]["error"])

    def test_different_reviewed_digest_blocks_registry_lookup(self):
        pinned = "example/image:latest@" + self.OLD
        calls = []
        _, report = updates.monitor(
            {pinned: ["x"]}, {"images": {"example/image:latest": self.NEW}},
            resolver=lambda tag: (calls.append(tag), None))
        self.assertEqual(calls, [])
        self.assertEqual(report["resolved"], 0)
        self.assertTrue(report["failed"])

    def test_changed_registry_digest_does_not_rewrite_approved_baseline(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            snapshot = root / "baseline.json"
            original = {"images": {"example/image:latest": self.OLD}}
            snapshot.write_text(json.dumps(original))
            pinned = "example/image:latest@" + self.OLD
            args = ["updates.py", "--snapshot", str(snapshot),
                    "--root", str(root),
                    "--output", str(root / "updates.json"),
                    "--summary", str(root / "updates.md")]
            with patch.object(updates, "apps", return_value=[]), \
                 patch.object(updates, "image_usage", return_value={pinned: ["x"]}), \
                 patch.object(updates, "digest", return_value=(self.NEW, None)), \
                 patch.object(sys, "argv", args):
                self.assertEqual(updates.main(), 0)
            self.assertEqual(json.loads(snapshot.read_text()), original)
            report = json.loads((root / "updates.json").read_text())
            self.assertEqual(report["changed"][0]["new"], self.NEW)
            self.assertEqual(json.loads((root / "updates-live-digests.json").read_text())
                             ["images"]["example/image:latest"], self.NEW)

    def test_registry_error_is_never_reported_as_clean(self):
        pinned = "example/image:latest@" + self.OLD
        _, report = updates.monitor(
            {pinned: ["x"]}, {"images": {"example/image:latest": self.OLD}},
            resolver=lambda tag: (None, "TOOMANYREQUESTS"))
        self.assertEqual(report["changed"], [])
        self.assertEqual(report["resolved"], 0)
        self.assertEqual(report["failed"][0]["error"], "TOOMANYREQUESTS")


if __name__ == "__main__":
    unittest.main()
