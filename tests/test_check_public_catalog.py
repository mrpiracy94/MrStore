"""Public status must match the exact security-approved app set, not only counts."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_public_catalog import verify_live


BASE = "https://example.invalid/MrStore"
PREFIX = "io.github.mrpiracy94."


def fixtures():
    return {
        BASE + "/store.json": {"version": 2},
        BASE + "/index.json": {"version": 2, "app_count": 2, "apps": [
            {"id": PREFIX + "immich"}, {"id": PREFIX + "nextcloud"}]},
        BASE + "/release-status.json": {
            "source_apps": 3, "approved_count": 2, "quarantined_count": 1,
            "approved": ["immich", "nextcloud"], "quarantined": {"unsafe": ["CVE"]},
        },
    }


class PublicCatalogTests(unittest.TestCase):
    def check(self, data):
        return verify_live(BASE, fetcher=lambda url: copy.deepcopy(data[url]))

    def test_complete_matching_selection(self):
        self.assertEqual(self.check(fixtures()),
                         {"approved": 2, "quarantined": 1, "total": 3})

    def test_equal_counts_with_wrong_approved_id_are_not_validated(self):
        data = fixtures()
        data[BASE + "/release-status.json"]["approved"] = ["immich", "jellyfin"]
        with self.assertRaisesRegex(ValueError, "IDs differ"):
            self.check(data)

    def test_duplicate_approved_slug_rejected(self):
        data = fixtures()
        data[BASE + "/release-status.json"]["approved"] = ["immich", "immich"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.check(data)

    def test_quarantined_app_cannot_be_approved(self):
        data = fixtures()
        data[BASE + "/release-status.json"]["quarantined"] = {
            "immich": ["CVE"]}
        with self.assertRaisesRegex(ValueError, "both approved"):
            self.check(data)

    def test_missing_evidence_fails_closed(self):
        data = fixtures()
        data.pop(BASE + "/release-status.json")
        with self.assertRaises(KeyError):
            self.check(data)

    def test_v2_only(self):
        data = fixtures()
        data[BASE + "/store.json"]["version"] = 1
        with self.assertRaisesRegex(ValueError, "protocol"):
            self.check(data)


if __name__ == "__main__":
    unittest.main()
