"""Tests: the storefront cannot alter the ZimaOS v2 release contract."""
import json
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

    def test_universal_selector_covers_eleven_platforms(self):
        html = (self.source / "index.html").read_text(encoding="utf-8")
        js = (self.source / "assets/site.js").read_text(encoding="utf-8")
        ids = ("zimaos", "homeio", "casaos", "umbrelos", "cosmos",
               "portainer", "homedock", "olares", "dockge", "runtipi", "docker-linux")
        for name in ids:
            self.assertIn(f'<option value="{name}">', html)
            self.assertIn(name + ":", js if name != "docker-linux" else js.replace('"docker-linux":', "docker-linux:"))
        self.assertIn('id="details-universal"', html)
        self.assertIn('fetch("./universal/catalog.json"', js)
        self.assertIn('catalog.approved_count !== expected.size', js)
        self.assertIn('selectedStoreURL', js)

    def test_native_downloads_are_security_gated(self):
        js = (self.source / "assets/site.js").read_text(encoding="utf-8")
        self.assertIn('fetch("./homedock/catalog.json"', js)
        self.assertIn('fetch("./olares/catalog.json"', js)
        self.assertIn('info.source_approved !== expected.size', js)
        self.assertIn('item.url !== "olares/" + item.chart + ".tgz"', js)
        self.assertIn('app.url !== "homedock/" + app.slug + ".hds"', js)
        self.assertIn('homedockPackages.has(slug)', js)
        self.assertIn('olaresCharts.has(slug)', js)
        self.assertIn('portable.hidden = !downloadable;', js)
        self.assertNotIn("innerHTML", js)

    def test_compatibility_counts_never_claim_real_installations(self):
        js = (self.source / "assets/site.js").read_text(encoding="utf-8")
        self.assertIn('fetch("./universal/support-report.json"', js)
        self.assertIn('item.native_certified !== false', js)
        self.assertIn('item.runtime_verified_count !== 0', js)
        self.assertIn('item.upgrade_verified_count !== 0', js)
        self.assertIn('data.security_selection_count !== state.apps.length', js)
        self.assertIn('platformEligibility = new Map()', js)

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
        self.assertIn("ADAPTADORES EXPERIMENTAIS · A VALIDAR", html)
        self.assertIn("ZimaOS v2", html)
        self.assertIn(".platform-grid{display:grid", css)
        self.assertIn("@media(max-width:960px)", css)
        for asset in ("mark.svg", "readme-banner.svg"):
            self.assertIn("MrStore", (self.source / "assets" / asset).read_text(encoding="utf-8"))
        for bad in ("https://cdn.", "https://fonts.googleapis.com", "unpkg.com"):
            self.assertNotIn(bad, html)


if __name__ == "__main__":
    unittest.main()
