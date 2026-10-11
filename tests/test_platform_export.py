"""Testes offline dos adaptadores; não instalam Docker nem acedem a NAS."""
from __future__ import annotations
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import App, apps
from platform_export import blockers, export, _native_compose, _umbrel_metadata, _matrix

class PlatformExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = {a.folder: a for a in apps(ROOT)}

    def test_entire_inventory_has_honest_status(self):
        names = {k: ["it-tools"] for k in ("umbrel", "casaos", "homeio", "docker")}
        data = _matrix(list(self.items.values()), names)
        self.assertGreaterEqual(data["source_apps"], 254)
        self.assertEqual(len(data["apps"]), len(self.items))
        self.assertEqual(data["device_installations_verified"], 0)
        self.assertEqual(data["certification"], "not_assessed")
        self.assertTrue(all(not a["runtime_verified"] for a in data["apps"]))
        self.assertTrue(all(not v["device_tested"] for a in data["apps"] for v in a["platforms"].values()))

    def test_initial_pilots_pass_static_policy(self):
        for name in ("it-tools", "uptime-kuma"):
            for platform in ("umbrel", "casaos", "homeio", "docker"):
                with self.subTest(name=name, platform=platform):
                    self.assertEqual(blockers(self.items[name], platform), [])

    def test_native_umbrel_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            export(ROOT, out)
            self.assertEqual(yaml.safe_load((out / "umbrel" / "umbrel-app-store.yml").read_text()),
                             {"id": "mrstore", "name": "MrStore"})
            for name in ("it-tools", "uptime-kuma"):
                folder = out / "umbrel" / ("mrstore-" + name)
                meta = yaml.safe_load((folder / "umbrel-app.yml").read_text())
                compose = yaml.safe_load((folder / "docker-compose.yml").read_text())
                self.assertEqual(meta["id"], folder.name)
                self.assertEqual(meta["manifestVersion"], 1)
                self.assertIn("app_proxy", compose["services"])
                self.assertNotIn("x-casaos", compose)
                self.assertNotIn("name", compose)
                self.assertNotIn("ports", compose["services"][name])
                self.assertNotIn("container_name", compose["services"][name])
                self.assertEqual(compose["services"]["app_proxy"]["environment"]["APP_PORT"],
                                 80 if name == "it-tools" else 3001)
            kuma = yaml.safe_load((out / "umbrel" / "mrstore-uptime-kuma" /
                                    "docker-compose.yml").read_text())
            self.assertEqual(kuma["services"]["uptime-kuma"]["volumes"][0]["source"],
                             "$" + "{APP_DATA_DIR}/data")

    def test_casaos_homeio_zip_package_only_selected_apps(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            export(ROOT, out, "casaos")
            with ZipFile(out / "casaos" / "mrstore-casaos.zip") as archive:
                names = set(archive.namelist())
                self.assertEqual({n for n in names if n.startswith("Apps/")},
                    {"Apps/it-tools/docker-compose.yml", "Apps/uptime-kuma/docker-compose.yml"})
                self.assertTrue({"README-COMPATIBILITY.txt", "store-config.json",
                                 "supported-languages.json", "category-list.json"} <= names)
                self.assertNotIn("Apps/actual-budget/docker-compose.yml", names)
                self.assertIsNone(archive.testzip())

    def test_blocks_elevated_privileges_and_unportable_storage(self):
        source = self.items["uptime-kuma"]
        data = copy.deepcopy(source.source)
        data["services"]["uptime-kuma"]["privileged"] = True
        data["services"]["uptime-kuma"]["volumes"].append({
            "type": "bind", "source": "/var/run/docker.sock", "target": "/var/run/docker.sock"})
        edited = App(source.folder, source.path, data, source.metadata)
        self.assertIn("elevated_privileges", blockers(edited, "umbrel"))
        self.assertIn("sensitive_host_mount", blockers(edited, "umbrel"))
        self.assertIn("nonportable_storage", blockers(edited, "homeio"))

    def test_blocks_mutable_image_and_credentials(self):
        source = self.items["it-tools"]
        data = copy.deepcopy(source.source)
        data["services"]["it-tools"]["image"] = "example.invalid/app:latest"
        data["services"]["it-tools"]["environment"] = [
            "ADMIN_PASSWORD=CHANGE_ME", "API_TOKEN=hardcoded"]
        edited = App(source.folder, source.path, data, source.metadata)
        issues = blockers(edited, "umbrel")
        self.assertIn("mutable_or_missing_image", issues)
        self.assertIn("placeholder_credentials", issues)
        self.assertIn("static_credentials_review", issues)

    def test_docker_export_relocates_host_paths(self):
        data = _native_compose(self.items["uptime-kuma"], "docker")
        self.assertNotIn("x-casaos", data)
        self.assertEqual(data["services"]["uptime-kuma"]["volumes"][0]["source"], "./data")
        self.assertEqual(data["services"]["uptime-kuma"]["ports"][0]["published"], "30004")

    def test_conversion_does_not_mutate_source(self):
        original = copy.deepcopy(self.items["uptime-kuma"].source)
        for platform in ("umbrel", "docker"):
            _native_compose(self.items["uptime-kuma"], platform)
        self.assertEqual(self.items["uptime-kuma"].source, original)

    def test_umbrel_manifest_has_no_default_password(self):
        manifest = _umbrel_metadata(self.items["it-tools"])
        self.assertEqual(manifest["defaultPassword"], "")
        self.assertEqual(manifest["defaultUsername"], "")
        self.assertEqual(manifest["id"], "mrstore-it-tools")
        self.assertIn("Not verified", manifest["releaseNotes"])

if __name__ == "__main__":
    unittest.main()
