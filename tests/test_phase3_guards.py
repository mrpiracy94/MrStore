"""Phase 3 guards for stable publication and independent Dockerfile security scans."""
from pathlib import Path
import sys
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import local_asset_missing


class Phase3ReleaseSafetyTests(unittest.TestCase):
    def test_builder_restores_python_before_inventory_and_publication(self):
        text = (ROOT / ".github/workflows/rollout-233.yml").read_text()
        build = text.index("Build official ZimaOS v2 catalog")
        restored = text.index("Restore verified Python runtime after external store builder")
        pip = text.index("Restore security inventory dependencies")
        verify = text.index("Verify complete published index")
        inventory = text.index("Attach all-image security inventory")
        self.assertTrue(build < restored < pip < verify < inventory)
        self.assertIn("python -m pip install -r requirements.txt", text[pip:verify])
        self.assertIn("import sys, yaml", text[pip:verify])

    def test_netbootxyz_icon_is_local_and_present(self):
        from yaml import safe_load
        path = ROOT / "Apps/netbootxyz/docker-compose.yml"
        doc = safe_load(path.read_text(encoding="utf-8"))
        meta = doc["x-casaos"]
        for field in ("icon", "thumbnail"):
            value = meta[field]
            self.assertIn("mrpiracy94/MrStore/main/Apps/netbootxyz/icon.svg", value)
            self.assertIsNone(local_asset_missing(value, ROOT))

    def test_base_scanner_tests_on_pr_and_scans_other_events(self):
        workflow = (ROOT / ".github/workflows/dockerfile-base-scan.yml").read_text()
        doc = yaml.load(workflow, Loader=yaml.BaseLoader)
        self.assertIn("pull_request", doc["on"])
        jobs = doc["jobs"]
        self.assertEqual(jobs["base_cves"]["needs"], "offline_tests")
        self.assertEqual(jobs["base_cves"]["if"], "github.event_name != 'pull_request'")
        self.assertEqual(jobs["base_cves"]["strategy"]["matrix"]["shard"], ["0", "1", "2", "3"])
        self.assertEqual(doc["permissions"]["contents"], "read")
        self.assertIn("audit_dockerfile_bases.py", str(jobs["base_cves"]["steps"]))


if __name__ == "__main__":
    unittest.main()
