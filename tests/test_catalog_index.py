"""Regressions for the read-only catalog navigator and curated-list checks."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog import apps
from catalog_index import create_index, filter_records, markdown, main


class CatalogIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = apps()
        cls.categories = json.loads((ROOT / "category-list.json").read_text(encoding="utf-8"))
        cls.recommendations = json.loads((ROOT / "recommend-list.json").read_text(encoding="utf-8"))
        featured_path = ROOT / "featured-apps.json"
        cls.featured = json.loads(featured_path.read_text()) if featured_path.exists() else None

    def index(self, **kwargs):
        return create_index(self.source, self.categories, self.recommendations,
                            self.featured, **kwargs)

    def test_all_254_apps_preserved_and_sorted(self):
        report = self.index()
        self.assertEqual(report["summary"]["total_apps"], 254)
        self.assertEqual(report["summary"]["selected_apps"], 254)
        self.assertEqual(len({x["slug"] for x in report["apps"]}), 254)
        self.assertEqual(report["summary"]["errors"], 0, report["findings"])
        self.assertFalse(report["runtime_verified"])
        self.assertFalse(report["cve_scanned"])

    def test_no_secret_values_or_host_paths_in_public_inventory(self):
        data = json.dumps(self.index(), ensure_ascii=False)
        for disallowed in ("CHANGE_ME", "DB_PASSWORD=", "/DATA/AppData/",
                           "/var/run/docker.sock", "POSTGRES_PASSWORD="):
            self.assertNotIn(disallowed, data)

    def test_architecture_and_category_filters(self):
        base = self.index()["apps"]
        first = base[0]
        category = first["category"]
        hits = filter_records(base, category=category, architecture=first["architectures"][0])
        self.assertIn(first, hits)
        self.assertTrue(all(x["category"] == category for x in hits))
        self.assertTrue(all(first["architectures"][0] in x["architectures"] for x in hits))

    def test_accent_insensitive_search(self):
        records = [{"title": "Fotografias e Música", "slug": "abc",
                    "category": "Media", "architectures": ["amd64"]}]
        self.assertEqual(filter_records(records, query="musica"), records)
        self.assertEqual(filter_records(records, query="inexistente"), [])

    def test_detects_missing_recommendation_without_suppressing_drift(self):
        bad = [{"id": 1, "name": "definitely-not-an-existing-application"}]
        result = create_index(self.source, self.categories, bad)
        self.assertIn("recommendation_missing", [f["code"] for f in result["findings"]])
        self.assertGreater(result["summary"]["errors"], 0)

    def test_detects_duplicate_category_and_bad_featured(self):
        entry = {"name": "Media", "count": 50}
        result = create_index(self.source, [entry, entry], [],
                              [{"appid": "nonexistent"}, {"appid": "nonexistent"}])
        codes = {f["code"] for f in result["findings"]}
        self.assertIn("category_duplicate", codes)
        self.assertIn("featured_missing", codes)
        self.assertIn("featured_duplicate", codes)

    def test_reports_mismatched_taxonomy_without_rewriting_manifests(self):
        result = create_index(self.source, [{"name": "Invented", "count": 254}], [])
        codes = {f["code"] for f in result["findings"]}
        self.assertIn("category_not_listed", codes)
        self.assertIn("category_unused", codes)
        self.assertIn("category_count_drift", codes)

    def test_cli_generates_both_reports_from_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "inventory.json"
            md_path = Path(tmp) / "inventory.md"
            result = main(["--root", str(ROOT), "--json", str(json_path),
                           "--markdown", str(md_path), "--search", "immich"])
            self.assertEqual(result, 0)
            parsed = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["summary"]["total_apps"], 254)
            self.assertEqual([a["slug"] for a in parsed["apps"]], ["immich"])
            self.assertIn("Inventário estático", md_path.read_text(encoding="utf-8"))
            self.assertIn("## Consistência", markdown(parsed))


if __name__ == "__main__":
    unittest.main()
