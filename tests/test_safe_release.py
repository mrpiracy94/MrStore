"""Fail-closed release policy regression suite: unsafe apps remain in the source."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import App
from release_catalog import read_evidence, stage, insecure_defaults
from release_scan import audit_shard, image_platforms


def fixture(name, images, arch=None, insecure=False):
    spec = {f"service{i}": {"image": image}
            for i, image in enumerate(images)}
    if insecure:
        spec["service0"]["environment"] = ["PASSWORD=CHANGE_ME"]
    source = {
        "name": name,
        "services": spec,
        "x-casaos": {
            "id": "io.github.mrpiracy94." + name, "main": "service0",
            "architectures": arch or ["amd64"], "version": "1.0.0",
            "tagline": {"en_US": "Original"},
        },
    }
    # The source formatter must retain quoted x-casaos.version.
    manifest = (
        f"name: {name}\nservices:\n"
        + "".join(f"  service{i}:\n    image: {image}\n" for i, image in enumerate(images))
        + "x-casaos:\n"
        + f"  id: io.github.mrpiracy94.{name}\n"
        + "  main: service0\n  architectures:\n"
        + "".join(f"    - {v}\n" for v in (arch or ["amd64"]))
        + '  version: "1.0.0"\n  tagline:\n    en_US: Original\n'
    )
    if insecure:
        manifest = manifest.replace("    image: " + images[0] + "\n",
                    "    image: " + images[0] + "\n    environment:\n      - PASSWORD=CHANGE_ME\n", 1)
    return App(name, Path("Apps") / name / "docker-compose.yml", source if not insecure else yaml.safe_load(manifest),
               yaml.safe_load(manifest)["x-casaos"]), manifest


class SafeReleaseTests(unittest.TestCase):
    def test_both_architectures_scan_same_immutable_digest(self):
        app, _ = fixture("demo", ["example/demo:1"], ["amd64", "arm64"])
        pin = "example/demo:1@sha256:" + "a" * 64
        calls = []
        def scanner(image, platform):
            calls.append((image, platform))
            return ([{"severity": "HIGH"}] if platform == "arm64" else []), None
        result = audit_shard([app], 0, 1,
                             resolver=lambda x: (pin, None), scanner=scanner)
        self.assertEqual(calls, [(pin, "amd64"), (pin, "arm64")])
        self.assertEqual(result["results"][0]["status"], "vulnerable")
        self.assertFalse(insecure_defaults(app))

    def test_missing_digest_does_not_call_scanner(self):
        app, _ = fixture("demo", ["example/demo:1"])
        result = audit_shard([app], 0, 1,
                             resolver=lambda _: (None, "rate limited"),
                             scanner=lambda *_args, **_kwargs: self.fail("Must not scan"))
        self.assertEqual(result["results"][0]["status"], "error")

    def test_unknown_security_evidence_fails_closed(self):
        app, _ = fixture("demo", ["example/demo:1"])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Missing/duplicate"):
                read_evidence([app], Path(tmp))

    def test_missing_architecture_is_rejected(self):
        app, _ = fixture("demo", ["example/demo:1"])
        broken = App(app.folder, app.path, app.source,
                     {**app.metadata, "architectures": ["sparc"]})
        with self.assertRaises(ValueError):
            image_platforms([broken])

    def test_partial_scan_never_approves_release(self):
        app, _ = fixture("demo", ["example/demo:1"], ["amd64", "arm64"])
        pin = "example/demo:1@sha256:" + "a" * 64
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "release-cves-shard-0.json"
            data = {"shard": 0, "shards": 1, "images_total": 1,
                    "images_checked": 1, "results": [
                        {"image": "example/demo:1", "pinned": pin, "status": "clean",
                         "error": None, "platforms": ["amd64", "arm64"],
                         "scans": {"amd64": {"status": "ok", "high": 0,
                                             "critical": 0, "error": None}}}
                    ]}
            file.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "partial architecture scan"):
                read_evidence([app], Path(tmp), shards=1)

    def test_high_vulnerability_report_cannot_lie_as_clean(self):
        app, _ = fixture("demo", ["example/demo:1"])
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "release-cves-shard-0.json").write_text(json.dumps({
                "shard": 0, "shards": 1, "images_total": 1, "images_checked": 1,
                "results": [{"image": "example/demo:1", "pinned": "example/demo:1@sha256:" + "a"*64,
                             "status": "clean", "error": None, "platforms": ["amd64"],
                             "scans": {"amd64": {"status": "ok", "high": 1, "critical": 0,
                                                 "error": None}}}]
            }))
            with self.assertRaisesRegex(ValueError, "dishonest status"):
                read_evidence([app], Path(tmp), shards=1)

    def test_quarantine_one_app_but_stage_one_clean(self):
        good, src_good = fixture("good", ["ghcr.io/vendor/good:1"])
        bad, src_bad = fixture("bad", ["ghcr.io/vendor/bad:1"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for app, source in ((good, src_good), (bad, src_bad)):
                path = root / "Apps" / app.folder / "docker-compose.yml"
                path.parent.mkdir(parents=True)
                path.write_text(source)
            for file in ("store-config.json", "supported-languages.json"):
                (root / file).write_text("{}")
            (root / "category-list.json").write_text("[]")
            (root / "recommend-list.json").write_text("[]")
            records = {
                "ghcr.io/vendor/good:1": {"safe": True, "pinned": "ghcr.io/vendor/good:1@sha256:"+"a"*64, "status": "clean"},
                "ghcr.io/vendor/bad:1": {"safe": False, "pinned": None, "status": "error"},
            }
            result = stage(root, records, root / "release-source",
                           {"good": "App good", "bad": "App bad"})
            self.assertEqual(result["approved"], ["good"])
            self.assertEqual(result["quarantined_count"], 1)
            self.assertFalse((root / "release-source" / "Apps" / "bad").exists())
            contents = yaml.safe_load((root / "release-source" / "Apps" / "good" / "docker-compose.yml").read_text())
            self.assertEqual(contents["services"]["service0"]["image"], records["ghcr.io/vendor/good:1"]["pinned"])
            self.assertTrue((root / "Apps" / "bad" / "docker-compose.yml").exists())

    def test_placeholder_secrets_are_not_published(self):
        app, _ = fixture("danger", ["example/app:1"], insecure=True)
        self.assertTrue(insecure_defaults(app))


if __name__ == "__main__":
    unittest.main()
