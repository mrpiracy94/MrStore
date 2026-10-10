"""Olares Helm chart generator excludes non-portable Compose configurations."""
import io
import tarfile
import unittest
import yaml

from scripts.export_olares_preview import convert, _name, create_tgz

SHA = "d" * 64


class OlaresDraftTests(unittest.TestCase):
    def doc(self):
        return {
            "x-casaos": {"id": "io.github.mrpiracy94.demo", "main": "server",
                         "port_map": "3000", "version": "1.2.3",
                         "architectures": ["amd64", "arm64"],
                         "title": {"en_US": "Demo"}},
            "services": {"server": {"image": "example/demo@sha256:" + SHA,
                                    "environment": ["TZ=Europe/Lisbon"],
                                    "ports": [{"published": "3000", "target": 80,
                                               "protocol": "tcp"}],
                                    "volumes": [{"type": "bind",
                                                 "source": "/DATA/AppData/demo/config",
                                                 "target": "/config"}]}}
        }

    def test_chart_for_single_http_service(self):
        chart = convert("demo", self.doc())
        self.assertEqual(set(chart), {"Chart.yaml", "OlaresManifest.yaml", "values.yaml",
                                      "owners", "templates/workload.yaml"})
        manifest = yaml.safe_load(chart["OlaresManifest.yaml"])
        self.assertEqual(manifest["olaresManifest.version"], "0.12.0")
        self.assertEqual(manifest["apiVersion"], "v3")
        self.assertEqual(manifest["permission"]["appData"], True)
        self.assertEqual(manifest["workloadReplicas"], {_name("demo"): 1})
        self.assertNotIn("{{", chart["OlaresManifest.yaml"].decode())
        workload = chart["templates/workload.yaml"].decode()
        self.assertIn("{{ .Values.userspace.appData }}/config", workload)
        self.assertIn("example/demo@sha256:" + SHA, workload)
        tgz = create_tgz(_name("demo"), chart)
        with tarfile.open(fileobj=io.BytesIO(tgz), mode="r:gz") as packed:
            self.assertEqual(len(packed.getmembers()), 5)

    def test_no_external_mount_multiservice_or_secret(self):
        doc = self.doc()
        doc["services"]["database"] = {"image": "example/db@sha256:" + SHA}
        self.assertIsNone(convert("demo", doc))
        doc = self.doc()
        doc["services"]["server"]["volumes"][0]["source"] = "/DATA/Media/Movies"
        self.assertIsNone(convert("demo", doc))
        doc = self.doc()
        doc["services"]["server"]["environment"] = ["PASSWORD=password"]
        self.assertIsNone(convert("demo", doc))

    def test_names_distinct_for_slug_variants(self):
        self.assertNotEqual(_name("my-app"), _name("myapp"))
        self.assertLessEqual(len(_name("long-long-long-long-slug")), 30)


if __name__ == "__main__":
    unittest.main()
