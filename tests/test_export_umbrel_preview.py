"""Umbrel source converter excludes unsafe or incompatible stacks."""
import unittest
from scripts.export_umbrel_preview import convert

SHA = "c" * 64


class UmbrelPreviewTests(unittest.TestCase):
    def doc(self):
        return {
            "x-casaos": {"id": "io.github.mrpiracy94.demo",
                         "main": "web", "port_map": "8080", "title": {"en_US": "Demo"}},
            "services": {"web": {
                "image": "example/web@sha256:" + SHA,
                "environment": ["TZ=Europe/Lisbon"],
                "ports": [{"published": "8080", "target": 80, "protocol": "tcp"}],
                "volumes": [{"type": "bind", "source": "/DATA/AppData/demo/config",
                             "target": "/config"}]
            }}
        }

    def test_manifest_and_mapped_storage(self):
        manifest, compose = convert("demo", self.doc())
        self.assertIn("id: mrstore-demo", manifest)
        self.assertIn("APP_HOST: mrstore-demo_web_1", compose)
        self.assertIn("APP_PORT: 80", compose)
        self.assertIn("$" + "{APP_DATA_DIR}/config", compose)
        self.assertIn("sha256:" + SHA, compose)

    def test_reject_multiservice_external_path_or_privilege(self):
        doc = self.doc()
        doc["services"]["db"] = {"image": "postgres@sha256:" + SHA}
        self.assertIsNone(convert("demo", doc))
        doc = self.doc()
        doc["services"]["web"]["volumes"][0]["source"] = "/DATA/Media/Movies"
        self.assertIsNone(convert("demo", doc))
        doc = self.doc()
        doc["services"]["web"]["privileged"] = True
        self.assertIsNone(convert("demo", doc))


if __name__ == "__main__":
    unittest.main()
