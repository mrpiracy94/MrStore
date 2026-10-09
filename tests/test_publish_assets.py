"""Regression tests for CI asset fixes."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
AMD64_ONLY = "audacity cura dolphin handbrake joplin modrinth mullvad-browser onlyoffice opera signal steam zotero".split()

class PublishAssetsTests(unittest.TestCase):
    def test_mrstore_icons_exist(self):
        for path in sorted((ROOT / "Apps").glob("*/docker-compose.yml")):
            metadata = yaml.safe_load(path.read_text(encoding="utf-8"))["x-casaos"]
            for key in ("icon", "thumbnail"):
                url = metadata.get(key, "")
                if "raw.githubusercontent.com/mrpiracy94/MrStore/main/" in url:
                    rel = url.split("/MrStore/main/", 1)[1]
                    with self.subTest(app=path.parent.name, asset=key):
                        self.assertTrue((ROOT / rel).is_file(), rel)

    def test_unsupported_arm64_is_not_advertised(self):
        for app in AMD64_ONLY:
            f = ROOT / "Apps" / app / "docker-compose.yml"
            metadata = yaml.safe_load(f.read_text(encoding="utf-8"))["x-casaos"]
            with self.subTest(app=app):
                self.assertEqual(metadata["architectures"], ["amd64"])

if __name__ == "__main__":
    unittest.main()
