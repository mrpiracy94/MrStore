"""Regression guard for temporary SteamOS retirement from active catalog."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog import apps, image_usage
from image_freshness import RETIRED_UPSTREAM


class RetiredSteamOSTests(unittest.TestCase):
    def test_retired_app_absent_but_steam_kept(self):
        names = {app.folder for app in apps(ROOT)}
        self.assertNotIn("steamos", names)
        self.assertIn("steam", names)
        self.assertFalse((ROOT / "Apps/steamos/docker-compose.yml").exists())

    def test_retired_image_excluded_from_active_scans_and_digest_baseline(self):
        ref = "lscr.io/linuxserver/steamos:latest"
        usage = image_usage(apps(ROOT))
        self.assertNotIn(ref, usage)
        queued = json.loads((ROOT / "data/cve-inconclusive-20261009.json").read_text())
        self.assertNotIn(ref, queued)
        baseline = json.loads((ROOT / "data/image-digests.json").read_text())
        self.assertNotIn(ref, baseline["images"])
        self.assertIn(ref, RETIRED_UPSTREAM)

    def test_retired_tagline_removed(self):
        taglines = json.loads((ROOT / "data/taglines-pt.json").read_text())
        self.assertNotIn("steamos", taglines)
        self.assertIn("steam", taglines)


if __name__ == "__main__":
    unittest.main()
