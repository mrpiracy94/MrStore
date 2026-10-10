"""Tests: the storefront cannot alter the ZimaOS v2 release contract."""
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from stage_storefront import stage, verify_release, ALLOWED, PREFIX


class StorefrontTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dist = Path(self.temp.name) / "dist"
        self.dist.mkdir()
        self.source = ROOT / "web"

    def approved(self):
        slugs = ["example", "other"]
        (self.dist / "store.json").write_text(json.dumps({"version": 2}))
        (self.dist / "index.json").write_text(json.dumps({
            "version": 2, "app_count": 2,
            "apps": [{"id": PREFIX + slug} for slug in slugs]}))
        (self.dist / "release-status.json").write_text(json.dumps({
            "approved_count": 2, "approved": slugs,
            "quarantined_count": 3, "quarantined": {"unsafe": ["CVE"]}}))

    def test_publication_preserves_official_protocol_bytes(self):
        self.approved()
        preserved = {p: (self.dist / p).read_bytes()
                     for p in ("store.json", "index.json", "release-status.json")}
        self.assertEqual(stage(self.source, self.dist), 2)
        for p, content in preserved.items():
            self.assertEqual((self.dist / p).read_bytes(), content)
        for p in ALLOWED:
            self.assertEqual((self.dist / p).read_bytes(), (self.source / p).read_bytes())

    def test_rejects_missing_security_evidence(self):
        (self.dist / "index.json").write_text(json.dumps({
            "version": 2, "app_count": 1, "apps": [{"id": PREFIX + "example"}]}))
        (self.dist / "store.json").write_text('{"version":2}')
        with self.assertRaisesRegex(ValueError, "release-status.json"):
            stage(self.source, self.dist)

    def test_rejects_mismatched_release_and_index(self):
        self.approved()
        (self.dist / "release-status.json").write_text(json.dumps({
            "approved_count": 2, "approved": ["example", "blocked"]}))
        with self.assertRaisesRegex(ValueError, "match"):
            stage(self.source, self.dist)

    def test_rejects_duplicate_or_empty_release(self):
        self.approved()
        (self.dist / "index.json").write_text(json.dumps({
            "version": 2, "app_count": 2, "apps": [{"id": PREFIX + "example"}] * 2}))
        with self.assertRaises(ValueError):
            verify_release(self.dist)
        (self.dist / "index.json").write_text(json.dumps({
            "version": 2, "app_count": 0, "apps": []}))
        (self.dist / "release-status.json").write_text(json.dumps({
            "approved_count": 0, "approved": []}))
        with self.assertRaises(ValueError):
            stage(self.source, self.dist)

    def test_does_not_overwrite_existing_builder_assets(self):
        self.approved()
        (self.dist / "index.html").write_text("original")
        with self.assertRaisesRegex(ValueError, "overwrite"):
            stage(self.source, self.dist)
        self.assertEqual((self.dist / "index.html").read_text(), "original")


    def test_platform_cards_use_genuine_versioned_brand_icons(self):
        html = (self.source / "index.html").read_text(encoding="utf-8")
        css = (self.source / "assets/site.css").read_text(encoding="utf-8")
        deployment = (ROOT / ".github/workflows/publish-storefront.yml").read_text(
            encoding="utf-8")
        official_blobs = {
            "platform-homeio.png": "0eeb090e1effe3d680ae943aceca2b9d43b717e1",
            "platform-homedock.svg": "61eeaa7877371e508daa2315142baf9bd42cd183",
            "platform-olares.svg": "05a864946511bf8f3554cf474dc20e0b63024e49",
        }
        for icon, expected_blob in official_blobs.items():
            with self.subTest(icon=icon):
                name = "assets/" + icon
                file = self.source / name
                self.assertTrue(file.is_file(), f"Official brand asset missing: {name}")
                data = file.read_bytes()
                self.assertTrue(data)
                self.assertLess(len(data), 50_000)
                git_blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
                self.assertEqual(hashlib.sha1(git_blob).hexdigest(), expected_blob)
                self.assertIn(f'src="./assets/{icon}"', html)
                self.assertIn(f'web/assets/{icon}', deployment)
                self.assertIn(f'assets/{icon}', deployment)
                self.assertIn(name, ALLOWED)
        self.assertTrue((self.source / "assets/platform-homeio.png").read_bytes()
                        .startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn(".system-glyph.platform-logo img", css)
        for label in ("Homeio", "HomeDock OS", "Olares"):
            self.assertIn(f"<strong>{label}</strong>", html)

    def test_ui_only_consumes_local_index_and_has_no_remote_dependencies(self):
        html = (self.source / "index.html").read_text(encoding="utf-8")
        js = (self.source / "assets/site.js").read_text(encoding="utf-8")
        css = (self.source / "assets/site.css").read_text(encoding="utf-8")
        self.assertIn('lang="pt-PT"', html)
        self.assertIn('Content-Security-Policy', html)
        self.assertIn('fetch("./index.json"', js)
        self.assertIn('fetch("./release-status.json"', js)
        self.assertIn('state.validated = verifyRelease', js)
        self.assertIn("textContent", js)
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("eval(", js)
        self.assertNotIn("new Function(", js)
        self.assertNotIn("@import", css)
        self.assertIn("@media(max-width:520px)", css)
        # HTML's hidden attribute must win over author-level flex/button CSS.
        self.assertIn("[hidden]{display:none!important}", css)
        self.assertIn('id="details-preview" hidden', html)
        self.assertIn("safePath(app.thumbnail)", js)
        self.assertIn("preview.replaceChildren()", js)
        self.assertIn('screenshot.addEventListener("error"', js)
        self.assertIn("#details-icon>.detail-icon-inner img", css)
        self.assertIn('const CATEGORY_SYMBOLS =', js)
        self.assertIn('const cover = element("div", "app-card-cover")', js)
        self.assertIn("shot.addEventListener(\"error\", coverFallback", js)
        self.assertIn("--orange:#ff831f", css)  # Identidade unificada em laranja.
        self.assertNotIn("--orange:#208bff", css)  # Evita regressões para o tema antigo.
        self.assertIn("grid-template-columns:repeat(8,minmax(0,1fr))", css)
        self.assertIn('id="ecossistema"', html)
        self.assertIn('class="mobile-nav"', html)
        self.assertIn('id="clear-filters"', html)
        self.assertIn('$("clear-filters").addEventListener("click"', js)
        self.assertIn('$("favorites-toggle").setAttribute("aria-pressed", "false")', js)
        self.assertIn("COMPATIBILIDADE · FORMATO ATUAL E PLATAFORMAS-ALVO", html)
        self.assertIn("ZimaOS App Store v2", html)
        self.assertIn("O teu catálogo.", html)
        self.assertNotIn("INTEGRAÇÃO ATUAL · ZIMAOS V2", html)
        self.assertIn("ZIMAOS_INSTALLATION.md", html)
        self.assertIn("O endereço público não é um instalador universal", html)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## 🌍 Plataformas e compatibilidade", readme)
        self.assertNotIn("## 🚀 Adicionar ao ZimaOS", readme)
        self.assertTrue((ROOT / "docs" / "ZIMAOS_INSTALLATION.md").is_file())
        self.assertIn('src="./assets/mrstore-hero.webp"', html)
        self.assertIn("hero-universe", html)
        self.assertIn("hero-banner-image", css)
        self.assertIn("assets/mrstore-hero.webp", ALLOWED)
        self.assertLessEqual((self.source / "assets/mrstore-hero.webp").stat().st_size, 250_000)
        self.assertEqual((self.source / "assets/mrstore-hero.webp").read_bytes()[:4], b"RIFF")
        self.assertIn(".platform-grid{display:grid", css)
        self.assertIn("@media(max-width:960px)", css)
        for asset in ("mark.svg", "readme-banner.svg"):
            self.assertIn("MrStore", (self.source / "assets" / asset).read_text(encoding="utf-8"))
        for bad in ("https://cdn.", "https://fonts.googleapis.com", "unpkg.com"):
            self.assertNotIn(bad, html)


if __name__ == "__main__":
    unittest.main()
