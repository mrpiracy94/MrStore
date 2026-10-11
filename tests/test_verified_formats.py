"""Restrict public compatibility claims to formats actually present in MrStore."""
from pathlib import Path
import json
import re
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
UNVERIFIED = ("UmbrelOS", "Homeio", "CasaOS", "Portainer", "Dockge",
              "Runtipi", "HomeDock OS", "Olares", "Cosmos")


class VerifiedFormatsTests(unittest.TestCase):
    def test_all_source_apps_remain_untouched(self):
        source = list((ROOT / "Apps").glob("*/docker-compose.yml"))
        self.assertEqual(len(source), 254)
        self.assertEqual(len({p.parent.name for p in source}), 254)
        self.assertTrue((ROOT / "Apps/jellyfin/docker-compose.yml").is_file())
        self.assertTrue((ROOT / "Apps/uptime-kuma/docker-compose.yml").is_file())

    def test_public_presentation_has_no_unsupported_native_store_claims(self):
        public = ((ROOT / "README.md").read_text(encoding="utf-8"),
                  (ROOT / "web/index.html").read_text(encoding="utf-8"),
                  json.dumps(json.loads((ROOT / "store-config.json").read_text()), ensure_ascii=False))
        for document in public:
            self.assertIn("ZimaOS", document)
            for name in UNVERIFIED:
                with self.subTest(platform=name):
                    self.assertNotIn(name, document)
            self.assertNotIn("mrstore-casaos.zip", document)
            self.assertNotIn("mrstore-homeio.zip", document)
        self.assertIn("Docker Compose", public[0])
        self.assertIn("Docker Compose", public[1])

    def test_no_unverified_exporter_or_pilot_publication(self):
        deprecated = (
            "scripts/platform_export.py", "data/platform-pilots.json",
            "tests/test_platform_export.py", ".github/workflows/platform-adapters.yml",
            ".github/workflows/vendor-platform-logos.yml", "docs/MULTIPLATFORM.md",
            "web/assets/platform-homeio.png", "web/assets/platform-homedock.svg",
            "web/assets/platform-olares.svg",
        )
        for item in deprecated:
            with self.subTest(deprecated=item):
                self.assertFalse((ROOT / item).exists())
        pipeline = (ROOT / ".github/workflows/rollout-233.yml").read_text()
        self.assertNotIn("platform_export.py", pipeline)
        self.assertNotIn("mrstore-casaos.zip", pipeline)
        self.assertNotIn("mrstore-homeio.zip", pipeline)
        self.assertIn("Build official ZimaOS v2 catalog", pipeline)
        self.assertIn("keep_files: false", pipeline)
        official = (ROOT / ".github/workflows/publish.yml").read_text()
        self.assertIn("Build official ZimaOS v2 catalog", official)

    def test_existing_publisher_still_validates_full_inventory(self):
        pipeline = (ROOT / ".github/workflows/rollout-233.yml").read_text(encoding="utf-8")
        self.assertIn("len(source) < 254", pipeline)
        self.assertIn("index.get('app_count')", pipeline)
        self.assertIn("not_assessed", pipeline)
        self.assertIn("scripts/stage_storefront.py", pipeline)
        self.assertIn("security-inventory.json", pipeline)

if __name__ == "__main__":
    unittest.main()
