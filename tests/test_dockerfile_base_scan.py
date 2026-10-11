"""Fail-closed tests for scanning first-party Dockerfile base images."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_dockerfile_bases import references, audit


class DockerfileBaseTests(unittest.TestCase):
    def test_multistage_and_default_arg(self):
        self.assertEqual(references("ARG BASE=alpine:3.20\nFROM $BASE AS build\nFROM build\n"),
                         ["alpine:3.20"])

    def test_unresolved_argument(self):
        self.assertEqual(references("ARG APP\nFROM docker.io/vendor/$APP:latest\n"),
                         ["docker.io/vendor/$APP:latest"])

    def _setup(self, folder, contents):
        path = Path(folder) / "security/images/example/Dockerfile"
        path.parent.mkdir(parents=True)
        path.write_text(contents)
        return Path(folder)

    def test_both_platforms_are_scanned(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._setup(d, "FROM alpine:3.20\n")
            seen = []
            def scanner(ref, platform):
                seen.append(platform)
                return [], None
            result = audit(root, 0, 1,
                           resolver=lambda r: (r + "@sha256:" + "a"*64, None),
                           scanner=scanner)
            self.assertEqual(result["results"][0]["status"], "clean")
            self.assertEqual(sorted(seen), ["amd64", "arm64"])

    def test_unknown_args_cannot_be_clean(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._setup(d, "ARG APP\nFROM docker.io/vendor/$APP:latest\n")
            result = audit(root, 0, 1,
                           resolver=lambda *_: self.fail("resolved dynamic ARG"),
                           scanner=lambda *_a, **_k: self.fail("scanned dynamic ARG"))
            self.assertEqual(result["results"][0]["status"], "needs_build_arg")

    def test_vulnerabilities_are_retained(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._setup(d, "FROM alpine:latest\n")
            result = audit(root, 0, 1,
                           resolver=lambda r: (r+"@sha256:"+"b"*64, None),
                           scanner=lambda ref, platform: ([{"severity":"HIGH"}], None))
            self.assertEqual(result["results"][0]["status"], "vulnerable")

    def test_registry_error_never_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._setup(d, "FROM alpine:latest\n")
            result = audit(root, 0, 1,
                           resolver=lambda r: (None, "registry unavailable"),
                           scanner=lambda *_a, **_k: self.fail("unexpected scan"))
            self.assertEqual(result["results"][0]["status"], "error")


if __name__ == "__main__":
    unittest.main()
