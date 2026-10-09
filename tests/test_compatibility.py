"""Regression tests for offline ZimaOS compatibility and read-only runtime evidence."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog import App, apps
from compatibility import inspect_app, inventory
from zimaos_runtime_probe import observed_port


class CompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_name = {app.folder: app for app in apps()}

    def test_inventory_never_claims_real_device_proof(self):
        report = inventory()
        self.assertEqual(report["total"], 254)
        self.assertEqual(report["runtime_verified"], 0)
        self.assertEqual(len(report["apps"]), 254)
        self.assertTrue(all(item["runtime_verified"] is False for item in report["apps"]))

    def test_nextcloud_uses_https_on_published_20019(self):
        item = inspect_app(self.by_name["nextcloud"])
        self.assertEqual(item["scheme"], "https")
        self.assertEqual(item["ui_port"], "20019")
        self.assertNotIn("launch_port_mismatch", [c["code"] for c in item["checks"]])

    def test_karakeep_public_url_matches_declared_port(self):
        item = inspect_app(self.by_name["karakeep"])
        self.assertNotIn("public_url_port_mismatch", [c["code"] for c in item["checks"]])
        self.assertEqual(item["status"], "configuration_required")
        env = self.by_name["karakeep"].source["services"]["karakeep"]["environment"]
        self.assertIn("NEXTAUTH_URL=http://zimaos.local:30002", env)

    def test_cloudflared_is_headless_not_web_verified(self):
        item = inspect_app(self.by_name["cloudflared"])
        self.assertEqual(item["status"], "headless_not_runtime_tested")
        self.assertFalse(item["runtime_verified"])

    def test_mismatched_launcher_port_is_caught(self):
        src = self.by_name["actual-budget"]
        changed = copy.deepcopy(src.source)
        changed["x-casaos"]["port_map"] = "9999"
        bad = App(src.folder, src.path, changed, changed["x-casaos"])
        item = inspect_app(bad)
        self.assertIn("launch_port_mismatch", [c["code"] for c in item["checks"]])
        self.assertEqual(item["status"], "static_review_required")

    def test_runtime_port_check_does_not_infer_ui_from_other_port(self):
        snapshot = {"running": True, "published": {
            "5006/tcp": [{"HostIp": "0.0.0.0", "HostPort": "5006"}],
            "5007/tcp": None,
        }}
        self.assertTrue(observed_port(snapshot, "5006"))
        self.assertFalse(observed_port(snapshot, "5007"))
        self.assertFalse(observed_port(snapshot, "5008"))


if __name__ == "__main__":
    unittest.main()
