"""Regression contract: discovery is never CVE certification or device proof."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from featured import load_featured
from rollout_233 import read_plan
from release_catalog import stage


class ReleaseStateContract(unittest.TestCase):
    def test_exact_233_selection_with_existing_unusual_slugs(self):
        source = {p.parent.name for p in (ROOT / "Apps").glob("*/docker-compose.yml")}
        selected = load_featured(ROOT / "data/featured-apps.json", source)
        plan = read_plan(ROOT / "data/rollout-233.json", source)
        self.assertGreaterEqual(len(selected), 233)
        self.assertEqual(len(plan), 233)
        # The branch can contain a larger editorial source snapshot while
        # the progressive public target remains exactly 233.
        self.assertTrue(set(plan).issubset(set(selected)))
        self.assertIn("changedetection.io", plan)
        self.assertIn("doplarr_rs", plan)
        self.assertNotIn("steamos", plan)

    def test_validation_rejects_traversal_lookalikes(self):
        known = {"demo", "changedetection.io", "doplarr_rs"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "list.json"
            for slug in ("../demo", "demo..x", "demo/", "demo\\x", ".demo", "demo."):
                path.write_text(json.dumps({
                    "schema": 1, "description": "Test", "apps": [slug]
                }), encoding="utf-8")
                with self.subTest(slug=slug), self.assertRaises(ValueError):
                    load_featured(path, known)

    def test_frontend_fails_closed_without_proof(self):
        js = (ROOT / "web/assets/site.js").read_text(encoding="utf-8")
        self.assertIn('release.certification !== "security_scanned"', js)
        self.assertIn("editorial shortlist AND all image platforms scanned clean", js)
        self.assertIn('fetch("./index.json"', js)
        self.assertIn('fetch("./release-status.json"', js)
        self.assertIn("NÃO equivale a testes de instalação", js)

    def test_security_release_still_requires_eight_shards(self):
        workflow = (ROOT / ".github/workflows/publish.yml").read_text()
        self.assertIn("security_audit:", workflow)
        self.assertIn("matrix:", workflow)
        self.assertIn("shard: [0, 1, 2, 3, 4, 5, 6, 7]", workflow)
        self.assertIn("needs: security_audit", workflow)
        self.assertIn("scripts/release_catalog.py --reports", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)

    def test_security_result_is_explicitly_not_runtime_certification(self):
        script = (ROOT / "scripts/release_catalog.py").read_text()
        self.assertIn('"certification": "security_scanned"', script)
        self.assertIn("no real-device install certification", script)
        stage_script = (ROOT / "scripts/publish_editorial.py").read_text()
        self.assertIn('"certification": "not_assessed"', stage_script)


if __name__ == "__main__":
    unittest.main()
