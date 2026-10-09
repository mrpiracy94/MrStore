"""Prevent regressions from historical MrStore PRs #1-#20.

All tests are static, without pulling images, running containers or touching
ZimaOS installations. A future tested migration may update these contracts.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import apps


class HistoricalPRSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = {app.folder: app for app in apps()}

    def test_pr1_is_replaced_by_migration_aware_pr24(self):
        """A Meilisearch tag-only upgrade could corrupt an existing installation."""
        service = self.entries["karakeep"].source["services"]["karakeep-meilisearch"]
        self.assertRegex(
            service["image"],
            r"^getmeili/meilisearch:v1\.54\.3@sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(service["command"], ["meilisearch", "--upgrade-db"])
        self.assertTrue(any(v["source"] == "/DATA/AppData/karakeep/meili"
                            and v["target"] == "/meili_data"
                            for v in service["volumes"]))
        self.assertTrue((ROOT / "docs/KARAKEEP_MEILI_MIGRATION.md").is_file())
        env_main = self.entries["karakeep"].source["services"]["karakeep"]["environment"]
        env_db = service["environment"]
        main_key = next(x.partition("=")[2] for x in env_main if x.startswith("MEILI_MASTER_KEY="))
        db_key = next(x.partition("=")[2] for x in env_db if x.startswith("MEILI_MASTER_KEY="))
        self.assertEqual(main_key, db_key)

    def test_pr5_does_not_perform_a_blind_postgres_major_upgrade(self):
        """PG14 data directory must not be mounted by a PG16 image without migration."""
        immich = self.entries["immich"].source["services"]
        db = immich["immich-database"]
        self.assertRegex(
            db["image"],
            r"^ghcr\.io/immich-app/postgres:14-vectorchord0\.4\.3-pgvectors0\.2\.0$",
        )
        self.assertTrue(any(v["source"] == "/DATA/AppData/immich/postgres"
                            and v["target"] == "/var/lib/postgresql/data"
                            for v in db["volumes"]))
        server_pw = next(x.split("=", 1)[1] for x in immich["immich-server"]["environment"]
                         if x.startswith("DB_PASSWORD="))
        db_pw = next(x.split("=", 1)[1] for x in db["environment"]
                     if x.startswith("POSTGRES_PASSWORD="))
        self.assertEqual(server_pw, db_pw)
        self.assertTrue(server_pw, "Never silently clear a DB password")

    def test_pr6_wrong_qbittorrent_20_04_1_version_cannot_return(self):
        """The LinuxServer 20.04.1 tag is not a qBittorrent 5.x version."""
        manifest = self.entries["qbittorrent-4"]
        spec = manifest.source["services"]["qbittorrent-4"]
        self.assertNotIn("20.04.1", spec["image"])
        self.assertRegex(
            spec["image"],
            r"^ghcr\.io/mrpiracy94/mrstore-qbittorrent:"
            r"5\.2\.4-libtorrentv1-secfix-20261009@sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(set(manifest.metadata["architectures"]), {"amd64", "arm64"})
        self.assertTrue(any(v["source"] == "/DATA/AppData/qbittorrent-4/config"
                            and v["target"] == "/config" for v in spec["volumes"]))
        self.assertTrue(any(v["source"] == "/DATA/Downloads"
                            and v["target"] == "/downloads" for v in spec["volumes"]))

    def test_pr13_actual_budget_official_registry_remains_selected(self):
        service = self.entries["actual-budget"].source["services"]["actual-budget"]
        self.assertEqual(service["image"], "ghcr.io/actualbudget/actual:latest")
        self.assertTrue(any(v["source"] == "/DATA/AppData/actual-budget"
                            for v in service["volumes"]))

    def test_pr10_frigate_stays_without_unrestricted_privilege(self):
        self.assertIsNot(self.entries["frigate"].source["services"]["frigate"].get("privileged"), True)

    def test_pr17_cve_audit_cancellation_only_for_push(self):
        path = (ROOT / ".github/workflows/cve-scan.yml").read_text(encoding="utf-8")
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'push' }}", path)


if __name__ == "__main__":
    unittest.main()
