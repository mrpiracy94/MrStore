"""A small public shop is an editorial allowlist, never a security bypass."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from featured import load_featured
from release_catalog import stage

STARTER = ROOT / "data/featured-apps.json"


class FeaturedCatalogTests(unittest.TestCase):
    def test_initial_selection_is_small_unique_and_from_existing_source(self):
        known = {x.parent.name for x in (ROOT / "Apps").glob("*/docker-compose.yml")}
        featured = load_featured(STARTER, known)
        self.assertEqual(len(featured), 32)
        self.assertGreater(len(known), len(featured))
        self.assertIn("jellyfin", featured)
        self.assertIn("immich", featured)
        self.assertIn("qbittorrent", featured)
        self.assertIn("uptime-kuma", featured)
        self.assertNotIn("steamos", featured)
        self.assertEqual(len(set(featured)), len(featured))

    def test_missing_duplicate_unknown_and_empty_allowlists_fail_closed(self):
        with TemporaryDirectory() as folder:
            policy = Path(folder) / "curation.json"
            with self.assertRaisesRegex(ValueError, "missing"):
                load_featured(policy)
            for slugs in ([], ["demo", "demo"], ["../bad"], ["unknown"]):
                with self.subTest(slugs=slugs):
                    policy.write_text(json.dumps({
                        "schema": 1, "description": "Curation", "apps": slugs}))
                    with self.assertRaises(ValueError):
                        load_featured(policy, {"demo"})

    def test_live_workflow_requires_featured_gate_after_eight_shard_scan(self):
        workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
        self.assertIn("--featured data/featured-apps.json", workflow)
        self.assertIn("scripts/release_catalog.py --reports", workflow)
        self.assertIn("scripts/release_scan.py --shards 8", workflow)
        self.assertIn("data/featured-apps.json", workflow)
        self.assertIn("scripts/featured.py", workflow)
        self.assertIn("scripts/verify_dist.py --expected", workflow)

    def test_staging_never_publishes_deferred_or_failed_featured_entries(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source, output = folder / "src", folder / "release"
            for slug in ("demo", "hidden", "unsafe"):
                path = source / "Apps" / slug
                path.mkdir(parents=True)
                doc = {
                    "name": slug,
                    "services": {"web": {"image": "example/" + slug + ":1"}},
                    "x-casaos": {"category": "Developer", "id": "io.github.mrpiracy94." + slug},
                }
                (path / "docker-compose.yml").write_text(yaml.safe_dump(doc))
            for meta in ("store-config.json", "supported-languages.json"):
                (source / meta).write_text("{}")
            (source / "category-list.json").write_text(json.dumps([
                {"name": "Developer", "count": 3}]))
            (source / "recommend-list.json").write_text(json.dumps([
                {"name": "demo"}, {"name": "hidden"}, {"name": "unsafe"}]))
            evidence = {
                "example/demo:1": {"safe": True,
                                   "pinned": "example/demo@sha256:" + "a"*64,
                                   "status": "clean"},
                "example/hidden:1": {"safe": False, "pinned": None,
                                     "status": "vulnerable"},
                "example/unsafe:1": {"safe": False, "pinned": None,
                                     "status": "vulnerable"},
            }
            with patch("release_catalog.render_manifest",
                       side_effect=lambda text, slug, summary: text):
                selected = stage(source, evidence, output, {"demo": "ok"},
                                 featured={"demo", "unsafe"})
            self.assertEqual(selected["source_apps"], 3)
            self.assertEqual(selected["featured_count"], 2)
            self.assertEqual(selected["approved_count"], 1)
            self.assertEqual(selected["quarantined_count"], 1)
            self.assertEqual(selected["deferred_count"], 1)
            self.assertEqual(selected["deferred"], ["hidden"])
            self.assertEqual(set(selected["quarantined"]), {"unsafe"})
            self.assertTrue((output / "Apps/demo/docker-compose.yml").is_file())
            self.assertFalse((output / "Apps/hidden").exists())
            self.assertFalse((output / "Apps/unsafe").exists())
            count = json.loads((output / "category-list.json").read_text())
            self.assertEqual(count[0]["count"], 1)
            rec = json.loads((output / "recommend-list.json").read_text())
            self.assertEqual([r["name"] for r in rec], ["demo"])

    def test_staging_rejects_empty_or_unknown_featured_policy(self):
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "src"
            (source / "Apps" / "demo").mkdir(parents=True)
            (source / "Apps" / "demo" / "docker-compose.yml").write_text(
                "services:\n  web:\n    image: example/demo:1\n")
            for selected in (set(), {"missing"}):
                with self.subTest(selected=selected):
                    with self.assertRaisesRegex(ValueError, "selection"):
                        stage(source, {}, Path(temporary) / "dist", {}, featured=selected)


if __name__ == "__main__":
    unittest.main()
