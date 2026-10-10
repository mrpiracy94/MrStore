"""Reject ambiguous duplicate YAML keys in every app's storefront metadata."""
from pathlib import Path
import unittest

import yaml
from yaml.nodes import MappingNode, ScalarNode


ROOT = Path(__file__).resolve().parents[1]


def storefront_node(path: Path):
    document = yaml.compose(path.read_text(encoding="utf-8"))
    if not isinstance(document, MappingNode):
        raise AssertionError(f"{path}: manifest must contain a YAML mapping")
    for key, value in document.value:
        if isinstance(key, ScalarNode) and key.value == "x-casaos":
            if not isinstance(value, MappingNode):
                raise AssertionError(f"{path}: invalid x-casaos metadata")
            return value
    raise AssertionError(f"{path}: missing x-casaos metadata")


def assert_no_duplicate_keys(testcase, node, prefix):
    if not isinstance(node, MappingNode):
        return
    seen = set()
    for key, value in node.value:
        if not isinstance(key, ScalarNode):
            continue
        label = key.value
        testcase.assertNotIn(label, seen, f"{prefix}: duplicate YAML key {label!r}")
        seen.add(label)
        assert_no_duplicate_keys(testcase, value, f"{prefix}.{label}")


class StorefrontMetadataUniquenessTests(unittest.TestCase):
    def test_every_app_metadata_has_unique_keys(self):
        files = sorted((ROOT / "Apps").glob("*/docker-compose.yml"))
        self.assertEqual(254, len(files))
        for path in files:
            with self.subTest(app=path.parent.name):
                assert_no_duplicate_keys(self, storefront_node(path), path.parent.name)


if __name__ == "__main__":
    unittest.main()
