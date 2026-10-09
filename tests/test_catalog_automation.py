"""Offline regression tests for non-deployment catalog automation."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_public_catalog import verify_live
from discover_apps import missing_candidates
from review_updates import classify


class CatalogOpsTests(unittest.TestCase):
    def test_public_catalog_matches_quarantine_status(self):
        docs = {
            "store.json": {"version": 2},
            "index.json": {"version": 2, "app_count": 2, "apps": [
                {"id": "io.github.mrpiracy94.a"}, {"id": "io.github.mrpiracy94.b"}]},
            "release-status.json": {"source_apps": 3, "approved_count": 2,
                                    "quarantined_count": 1, "approved": ["a", "b"],
                                    "quarantined": {"c": ["HIGH"]}},
        }
        fetch = lambda url: docs[url.rsplit("/", 1)[-1]]
        self.assertEqual(verify_live("https://example.test", fetch)["approved"], 2)
        docs["release-status.json"]["quarantined_count"] = 0
        with self.assertRaisesRegex(ValueError, "Inconsistent"):
            verify_live("https://example.test", fetch)

    def test_duplicate_app_id_is_rejected(self):
        entry = {"id": "a"}
        fetch = lambda url: ({
            "store.json": {"version": 2},
            "index.json": {"version": 2, "app_count": 2, "apps": [entry, entry]},
            "release-status.json": {"source_apps": 2, "approved_count": 2,
                                    "quarantined_count": 0, "approved": ["a", "b"],
                                    "quarantined": {}},
        })[url.rsplit("/", 1)[-1]]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            verify_live("https://example.test", fetch)

    def test_maintained_candidate_list_is_validated(self):
        proposals = json.loads((ROOT / "data/app-candidates.json").read_text())
        found = missing_candidates(ROOT)
        self.assertTrue({x["slug"] for x in found} <= {x["slug"] for x in proposals})

    def test_database_upgrade_requires_review(self):
        previous = {"services": {"postgres": {"image": "postgres:16"}}}
        current = {"services": {"postgres": {"image": "postgres:17"}}}
        result = classify(previous, current, "db-app")
        self.assertEqual(result["risk"], "high")
        self.assertTrue(any("database" in x for x in result["reasons"]))


if __name__ == "__main__":
    unittest.main()
