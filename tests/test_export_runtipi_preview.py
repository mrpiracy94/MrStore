"""Conservative Runtipi preview emits required metadata and x-runtipi."""
import json
import unittest
import yaml

from scripts.export_runtipi_preview import convert_tipi, LOGO_JPG


class RuntipiTests(unittest.TestCase):
    def test_single_service_and_metadata(self):
        manifest = {
            "x-casaos": {"id": "io.github.mrpiracy94.example", "main": "web",
                         "port_map": "8080", "version": "1.0.0",
                         "architectures": ["amd64", "arm64"]},
            "services": {"web": {"image": "example@sha256:" + "a" * 64,
                                 "ports": [{"published": "8080", "target": 80}],
                                 "volumes": [{"type": "bind", "source": "/DATA/AppData/example/data",
                                              "target": "/data"}]}}
        }
        data = convert_tipi("example", manifest)
        self.assertEqual(len(data), 4)
        config = json.loads(data["apps/example/config.json"])
        self.assertEqual(config["id"], "example")
        self.assertEqual(config["supported_architectures"], ["amd64", "arm64"])
        compose = yaml.safe_load(data["apps/example/docker-compose.yml"])
        self.assertEqual(compose["x-runtipi"]["schema_version"], 2)
        self.assertEqual(compose["services"]["web"]["x-runtipi"]["internal_port"], 80)
        self.assertTrue(LOGO_JPG.startswith(b"\xff\xd8"))
        self.assertTrue(LOGO_JPG.endswith(b"\xff\xd9"))


if __name__ == "__main__":
    unittest.main()
