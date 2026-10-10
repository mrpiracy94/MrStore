"""The seven-app ZimaOS pilot must never imply a verified installation."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog import apps
from zimaos_pilot import PILOT_APPS, inspect_pilot_app, make_report, markdown, valid_host


class ZimaosPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = apps()
        cls.by_name = {a.folder: a for a in cls.items}

    def test_list_is_exactly_seven_and_matches_real_manifests(self):
        self.assertEqual(len(PILOT_APPS), 7)
        self.assertEqual(len(set(PILOT_APPS)), 7)
        self.assertTrue(set(PILOT_APPS) <= set(self.by_name))
        for name in PILOT_APPS:
            self.assertIn(self.by_name[name].metadata["main"],
                          self.by_name[name].source["services"])

    def test_reject_credentials_urls_ports_and_paths(self):
        self.assertTrue(valid_host("192.168.1.10"))
        self.assertTrue(valid_host("zimaos.local"))
        for host in ("http://nas", "192.168.1.10:5006", "user:pass@nas",
                     "nas.local/path", "nas?secret=x", "-nas", "nas..local", ""):
            with self.subTest(host=host):
                self.assertFalse(valid_host(host))

    def test_report_all_services_and_c3_remains_unverified(self):
        observed_urls = []
        all_ports = [
            {"HostPort": str(self.by_name[name].metadata["port_map"])}
            for name in PILOT_APPS
        ]
        def inspector(_name):
            return {"running": True, "published": {"80/tcp": all_ports}}
        def probe(url, timeout):
            observed_urls.append((url, timeout))
            return True, 200
        result = make_report(self.items, "private-nas.local",
                             inspector=inspector, prober=probe)
        self.assertEqual(result["pilot_total"], 7)
        self.assertEqual(result["c2_candidates"], 7)
        self.assertEqual(result["c2_certified"], 0)
        self.assertEqual(result["c3_certified"], 0)
        self.assertEqual(result["c4_certified"], 0)
        self.assertFalse(result["zimaos_store_installation_verified"])
        self.assertEqual(len(observed_urls), 7)
        self.assertNotIn("private-nas.local", str(result))
        self.assertNotIn("private-nas.local", markdown(result))
        for entry in result["results"]:
            self.assertFalse(entry["functional_c3_verified"])
            self.assertFalse(entry["persistence_verified"])
            self.assertFalse(entry["installed_via_zimaos_verified"])
            self.assertTrue(entry["manual_verification_required"])

    def test_unavailable_dependency_prevents_candidate(self):
        app = self.by_name["immich"]
        missing = next(
            spec["container_name"] for name, spec in app.source["services"].items()
            if name != app.metadata["main"]
        )
        def inspector(name):
            if name == missing:
                raise RuntimeError("contains private Docker host info")
            return {"running": True, "published": {
                "2283/tcp": [{"HostPort": "2283"}]
            }}
        record = inspect_pilot_app(
            app, "localhost", inspector=inspector, prober=lambda *_: (True, 200))
        self.assertFalse(record["all_services_running"])
        self.assertFalse(record["c2_candidate"])
        self.assertNotIn("private Docker host info", str(record))
        self.assertIn("error", next(v for v in record["services"].values()
                                    if not v["observed"]))

    def test_skipped_http_never_claims_c2(self):
        app = self.by_name["actual-budget"]
        def inspector(name):
            return {"running": True, "published": {
                "5006/tcp": [{"HostPort": "5006"}]
            }}
        record = inspect_pilot_app(app, "localhost", inspector=inspector,
                                   prober=lambda *_: self.fail("HTTP must be skipped"),
                                   skip_http=True)
        self.assertTrue(record["main_port_observed"])
        self.assertFalse(record["http_reachable"])
        self.assertFalse(record["c2_candidate"])


if __name__ == "__main__":
    unittest.main()
