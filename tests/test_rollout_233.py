"""Offline tests for reversible, cumulative 12-app public rollout."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from rollout_233 import BATCH, INITIAL, PREFIX, TARGET, curate, milestones, read_plan


def fixture(base: Path, extra=False):
    names = list(INITIAL) + [f"app{i:03d}" for i in range(TARGET - len(INITIAL))]
    dist = base / "dist"
    dist.mkdir()
    (dist / "apps").mkdir()
    ids = [PREFIX + slug for slug in names]
    index = {"version": 2, "app_count": TARGET, "apps": [{"id": app} for app in ids]}
    pt = {"apps": [{"id": app} for app in ids]}
    (dist / "index.json").write_text(json.dumps(index))
    (dist / "index.pt_PT.json").write_text(json.dumps(pt))
    (dist / "store.json").write_text('{"version":2}')
    (dist / "index.html").write_text("<main>Store</main>")
    (dist / "release-status.json").write_text(json.dumps({
        "certification": "not_assessed", "approved": names, "approved_count": TARGET}))
    for app in ids:
        folder = dist / "apps" / app
        folder.mkdir()
        (folder / "meta.json").write_text(json.dumps({"id": app}))
    with tarfile.open(dist / "metadata.tar.gz", "w:gz") as archive:
        members = {
            "index.json": json.dumps(index).encode(),
            "index.pt_PT.json": json.dumps(pt).encode(),
            **{f"apps/{app}/meta.json": json.dumps({"id": app}).encode() for app in ids}
        }
        if extra:
            members["unexpected.json"] = b'{"id":"' + ids[-1].encode() + b'"}'
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    (dist / "metadata.sha256").write_text(
        hashlib.sha256((dist / "metadata.tar.gz").read_bytes()).hexdigest()
        + "  metadata.tar.gz\n")
    return dist, names


class ProgressiveCatalogTests(unittest.TestCase):
    def test_milestones_and_selections(self):
        self.assertEqual(milestones(), list(range(18, 223, 12)) + [233])
        steps = milestones()
        self.assertEqual(len(steps), 19)
        self.assertEqual(steps[-1] - steps[-2], 11)
        self.assertEqual(steps[0] - len(INITIAL), BATCH)

    def test_main_rollout_file_has_233_valid_apps(self):
        data = read_plan(ROOT / "data/rollout-233.json", {
            f.parent.name for f in (ROOT / "Apps").glob("*/docker-compose.yml")})
        self.assertEqual(len(data), TARGET)
        self.assertFalse("steamos" in data)
        self.assertTrue(set(INITIAL) <= set(data[:6]))

    def test_stage_is_cumulative_and_preserves_tar_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dist, names = fixture(root)
            for count in (18, 222, 233):
                output = root / f"out-{count}"
                status = curate(dist, output, names, count)
                self.assertEqual(status["stage"], count)
                self.assertEqual(status["certification"], "not_assessed")
                expected = {PREFIX + slug for slug in names[:count]}
                main = json.loads((output / "index.json").read_text())
                self.assertEqual(main["app_count"], count)
                self.assertEqual({item["id"] for item in main["apps"]}, expected)
                self.assertEqual(len(list((output / "apps").iterdir())), count)
                self.assertEqual(json.loads((output / "release-status.json").read_text())
                                 ["certification"], "not_assessed")
                with tarfile.open(output / "metadata.tar.gz", "r:gz") as arc:
                    included = {m.split("/")[1] for m in arc.getnames()
                                if m.startswith("apps/")}
                    self.assertEqual(included, expected)
                self.assertEqual(
                    hashlib.sha256((output / "metadata.tar.gz").read_bytes()).hexdigest(),
                    (output / "metadata.sha256").read_text().split()[0])

    def test_reject_invalid_count_checksum_and_claimed_certification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dist, names = fixture(root)
            with self.assertRaisesRegex(ValueError, "milestone"):
                curate(dist, root / "bad", names, 19)
            (dist / "metadata.sha256").write_text("0"*64 + "  metadata.tar.gz\n")
            with self.assertRaisesRegex(ValueError, "checksum"):
                curate(dist, root / "bad2", names, 18)
            (dist / "metadata.sha256").write_text(
                hashlib.sha256((dist / "metadata.tar.gz").read_bytes()).hexdigest()
                + "  metadata.tar.gz\n")
            (dist / "release-status.json").write_text(
                '{"certification":"verified"}')
            with self.assertRaisesRegex(ValueError, "security-certified"):
                curate(dist, root / "bad3", names, 18)

    def test_unknown_embedded_app_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dist, names = fixture(root, extra=True)
            with self.assertRaisesRegex(ValueError, "Unrecognized reference"):
                curate(dist, root / "bad", names, 18)
            self.assertFalse((root / "bad").exists())


if __name__ == "__main__":
    unittest.main()
