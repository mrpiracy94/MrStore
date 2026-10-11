"""Testes offline da política multi-imagem (sem Docker)."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from security_inventory import (
    BLOCK_NEW, check_dockerfile, check_manifest, inventory, regression_keys,
    markdown,
)

A = "sha256:" + "a" * 64


def issues_of(doc, slug="demo", digests=None):
    return check_manifest(doc, slug, digests)


class SecurityInventoryTest(unittest.TestCase):
    def test_placeholder_secret_is_named_but_never_printed(self):
        doc = {"services": {"db": {"image": "postgres:17",
                "environment": ["POSTGRES_PASSWORD=CHANGE_ME", "FOO=CHANGE_ME"]}}}
        rows = issues_of(doc)
        self.assertEqual([x["code"] for x in rows if x["code"] == "credential_placeholder"],
                         ["credential_placeholder"])
        self.assertIn("POSTGRES_PASSWORD", json.dumps(rows))
        self.assertNotIn("CHANGE_ME", json.dumps(rows))

    def test_weak_known_example(self):
        doc = {"services": {"a": {"image": "demo:1",
                "environment": {"ADMIN_PASSWORD": "admin"}}}}
        self.assertIn("weak_example_secret", {r["code"] for r in issues_of(doc)})

    def test_password_access_flag_not_mistaken_for_secret(self):
        doc = {"services": {"ssh": {"image": "linuxserver/openssh-server",
                "environment": ["PASSWORD_ACCESS=true"]}}}
        self.assertNotIn("credential_placeholder", {r["code"] for r in issues_of(doc)})

    def test_public_sensitive_port_but_not_local_binding(self):
        exposed = {"services": {"web": {"image": "x:1",
                   "ports": [{"target": 80, "published": "5001", "protocol": "tcp"}]}}}
        self.assertIn("public_sensitive_ui",
                      {r["code"] for r in issues_of(exposed, "dockge")})
        exposed["services"]["web"]["ports"][0]["host_ip"] = "127.0.0.1"
        self.assertNotIn("public_sensitive_ui",
                         {r["code"] for r in issues_of(exposed, "dockge")})

    def test_socket_read_only_is_still_host_risk(self):
        doc = {"services": {"monitor": {"image": "demo:1", "volumes": [
            {"type": "bind", "source": "/var/run/docker.sock",
             "target": "/var/run/docker.sock", "read_only": True}]}}}
        self.assertIn("sensitive_bind", {r["code"] for r in issues_of(doc)})

    def test_privileged_host_and_seccomp(self):
        doc = {"services": {"x": {"image": "demo:1", "privileged": True,
              "network_mode": "host", "security_opt": ["seccomp:unconfined"]}}}
        self.assertTrue({"privileged", "host_network", "seccomp_unconfined"}
                        <= {r["code"] for r in issues_of(doc)})

    def test_digest_baseline_missing_and_match(self):
        doc = {"services": {"x": {"image": "example:1"}}}
        self.assertNotIn("unknown_image_digest",
                         {r["code"] for r in issues_of(doc, digests={"example:1": A})})
        self.assertIn("unknown_image_digest",
                      {r["code"] for r in issues_of(doc, digests={})})
        doc["services"]["x"]["image"] = "example:1@" + A
        self.assertNotIn("unknown_image_digest",
                         {r["code"] for r in issues_of(doc, digests={"example:1": A})})

    def test_dockerfile_stages_are_not_external_images(self):
        rows, bases = check_dockerfile(
            "FROM node:22-alpine AS build\n"
            "FROM build AS middle\n"
            "FROM alpine:3.20@sha256:" + "a" * 64 + "\n", "security/images/x/Dockerfile")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "floating_dockerfile_base")
        self.assertEqual(len(bases), 2)

    def test_dynamic_dockerfile_base_is_unverified(self):
        rows, _ = check_dockerfile("ARG APP\nFROM lscr.io/linuxserver/$APP:latest\n",
                                   "security/images/x/Dockerfile")
        self.assertEqual([r["code"] for r in rows], ["unresolved_dockerfile_base"])

    def test_regression_gate_grandfathers_legacy_and_blocks_new(self):
        old = issues_of({"services": {"app": {"image": "x:1",
             "environment": ["DB_PASSWORD=CHANGE_ME"]}}})
        fresh = issues_of({"services": {"app": {"image": "x:1",
             "environment": ["DB_PASSWORD=CHANGE_ME"],
             "privileged": True}}})
        self.assertEqual(
            {x[2] for x in regression_keys(fresh) - regression_keys(old)},
            {"privileged"})
        self.assertFalse(regression_keys(old) - regression_keys(old))
        self.assertTrue("credential_placeholder" in BLOCK_NEW)

    def test_complete_catalog_and_derived_dockerfiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Apps/test").mkdir(parents=True)
            (root / "Apps/test/docker-compose.yml").write_text(
                "name: test\nservices:\n  test:\n    image: example:1\n")
            (root / "data").mkdir()
            (root / "data/image-digests.json").write_text(
                json.dumps({"images": {"example:1": A}}))
            (root / "security/images/test").mkdir(parents=True)
            (root / "security/images/test/Dockerfile").write_text(
                "FROM alpine:3.20\n")
            result = inventory(root)
            self.assertEqual((result["apps_total"], result["unique_images_total"],
                              result["dockerfiles_total"]), (1, 1, 1))
            self.assertEqual(result["certification"], "not_assessed")
            self.assertIn("floating_dockerfile_base", result["counts_by_rule"])
            self.assertIn("auditoria", markdown(result, []).lower())


if __name__ == "__main__":
    unittest.main()
