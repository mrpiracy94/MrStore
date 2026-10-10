"""Guard ZimaOS persistent PG14 data from in-place major upgrades."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import apps
from review_updates import _pg_major, classify, immich_major_upgrade_hazards


class ImmichPostgresGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = next(a.source for a in apps() if a.folder == "immich")

    def test_actual_manifests_use_pg14_persistent_volume(self):
        service = self.original["services"]["immich-database"]
        self.assertEqual(_pg_major(service["image"]), 14)
        volume = next(x for x in service["volumes"]
                      if x["target"] == "/var/lib/postgresql/data")
        self.assertEqual(volume["source"], "/DATA/AppData/immich/postgres")
        self.assertFalse(immich_major_upgrade_hazards(self.original,
                                                       self.original, "immich"))

    def test_direct_major_upgrade_is_rejected_even_if_tag_looks_valid(self):
        new = copy.deepcopy(self.original)
        new["services"]["immich-database"]["image"] = (
            "ghcr.io/immich-app/postgres:16-vectorchord0.4.3-pgvectors0.2.0")
        hazards = immich_major_upgrade_hazards(self.original, new, "immich")
        self.assertEqual(len(hazards), 1)
        self.assertIn("14->16", hazards[0])
        self.assertIn("previous/missing data directory", hazards[0])
        self.assertEqual(classify(self.original, new, "immich")["risk"], "high")

    def test_equivalent_linux_path_alias_cannot_bypass_upgrade_guard(self):
        for alias in (
            "/DATA/AppData/immich/postgres/.",
            "/DATA/AppData/immich/./postgres",
            "/DATA/AppData/immich/postgres/../postgres",
            "//DATA//AppData/immich/postgres",
        ):
            with self.subTest(alias=alias):
                changed = copy.deepcopy(self.original)
                db = changed["services"]["immich-database"]
                db["image"] = "ghcr.io/immich-app/postgres:16-vectorchord0.4.3"
                db["volumes"][0]["source"] = alias
                self.assertTrue(
                    immich_major_upgrade_hazards(self.original, changed, "immich")
                )

    def test_overlapping_parent_or_child_directories_are_rejected(self):
        for candidate in (
            "/DATA/AppData/immich",
            "/DATA/AppData/immich/postgres/pg16",
            "/DATA/AppData/immich/postgres/pg16/../data",
        ):
            with self.subTest(candidate=candidate):
                changed = copy.deepcopy(self.original)
                db = changed["services"]["immich-database"]
                db["image"] = "ghcr.io/immich-app/postgres:16-vectorchord0.4.3"
                db["volumes"][0]["source"] = candidate
                self.assertTrue(immich_major_upgrade_hazards(
                    self.original, changed, "immich"))

    def test_removed_or_renamed_database_service_cannot_bypass_migration_guard(self):
        for replacement in (None, "postgres16", "immich-db-new"):
            with self.subTest(replacement=replacement):
                candidate = copy.deepcopy(self.original)
                service = candidate["services"].pop("immich-database")
                if replacement is not None:
                    service["image"] = "ghcr.io/immich-app/postgres:16-vectorchord0.4.3"
                    candidate["services"][replacement] = service
                warnings = immich_major_upgrade_hazards(
                    self.original, candidate, "immich")
                self.assertEqual(len(warnings), 1, warnings)
                self.assertIn("removed or renamed", warnings[0])

    def test_missing_data_mount_is_rejected(self):
        new = copy.deepcopy(self.original)
        db = new["services"]["immich-database"]
        db["image"] = "ghcr.io/immich-app/postgres:16-vectorchord0.4.3"
        db["volumes"] = []
        self.assertTrue(immich_major_upgrade_hazards(self.original, new, "immich"))

    def test_new_isolated_directory_requires_separate_migration_review(self):
        new = copy.deepcopy(self.original)
        db = new["services"]["immich-database"]
        db["image"] = "ghcr.io/immich-app/postgres:16-vectorchord0.4.3"
        db["volumes"][0]["source"] = "/DATA/AppData/immich/postgres16-restore"
        # No in-place disaster; normal high-risk migration review and C3 still
        # needed, so this is NOT approval of deployment or a successful restore.
        self.assertFalse(immich_major_upgrade_hazards(self.original, new, "immich"))
        self.assertEqual(classify(self.original, new, "immich")["risk"], "high")

    def test_switch_to_unrecognised_database_image_on_old_volume_blocked(self):
        new = copy.deepcopy(self.original)
        new["services"]["immich-database"]["image"] = "postgres:16-alpine"
        findings = immich_major_upgrade_hazards(self.original, new, "immich")
        self.assertEqual(len(findings), 1)
        self.assertIn("unknown", findings[0])

    def test_downgrade_same_directory_is_also_rejected(self):
        old = copy.deepcopy(self.original)
        old["services"]["immich-database"]["image"] = (
            "ghcr.io/immich-app/postgres:16-vectorchord0.4.3")
        self.assertTrue(immich_major_upgrade_hazards(old, self.original, "immich"))

    def test_other_apps_and_patch_tags_unaffected(self):
        new = copy.deepcopy(self.original)
        new["services"]["immich-database"]["image"] = (
            "ghcr.io/immich-app/postgres:14-vectorchord0.4.4-pgvectors0.2.0")
        self.assertFalse(immich_major_upgrade_hazards(self.original, new, "immich"))
        new["services"]["immich-database"]["image"] = (
            "ghcr.io/immich-app/postgres:16-vectorchord0.4.3")
        self.assertFalse(immich_major_upgrade_hazards(self.original, new, "another-app"))


if __name__ == "__main__":
    unittest.main()
