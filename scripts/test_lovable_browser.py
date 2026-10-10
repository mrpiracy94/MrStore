"""Real-browser smoke test of the Lovable-inspired MrStore front end.

Uses isolated synthetic fixtures; never represents the approved production release.
Captures desktop/mobile screenshots for direct design review in GitHub Actions.
"""
import json
from pathlib import Path
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from stage_storefront import PREFIX, stage  # noqa: E402

SOURCE = ROOT / "web"
ARTIFACTS = ROOT / "ui-screenshots"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


with tempfile.TemporaryDirectory(prefix="mrstore-ui-fixture-") as temp:
    dist = Path(temp)
    slugs = ("plex", "immich", "nextcloud", "jellyfin")
    categories = ("Media", "Media", "Productivity", "Media")
    apps = [
        {"id": PREFIX + slug, "title": slug.capitalize(),
         "category": category, "tagline": "Exemplo de aplicação do teste de interface",
         "architectures": ["amd64", "arm64"], "version": "1.0.0",
         "developer": "Fixture de teste", "icon": "", "thumbnail": "",
         "compose_url": "/apps/" + PREFIX + slug + "/docker-compose.yml"}
        for slug, category in zip(slugs, categories)
    ]
    (dist / "index.json").write_text(
        json.dumps({"version": 2, "app_count": len(apps), "apps": apps}), encoding="utf-8")
    (dist / "store.json").write_text(json.dumps({"version": 2}), encoding="utf-8")
    (dist / "release-status.json").write_text(json.dumps({
        "approved_count": len(slugs), "approved": list(slugs),
        "quarantined_count": 0, "quarantined": {}
    }), encoding="utf-8")
    assert stage(SOURCE, dist) == len(slugs)

    handler = lambda *args, **kwargs: Handler(*args, directory=str(dist), **kwargs)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for width, height in ((1536, 864), (390, 844)):
                page = browser.new_page(
                    viewport={"width": width, "height": height},
                    device_scale_factor=1,
                    reduced_motion="reduce")
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="networkidle")
                page.locator(".app-card").first.wait_for()
                assert page.locator(".chip").count() == 8
                assert page.locator(".app-card").count() == 4
                assert "Aplicações em destaque" in page.locator("#catalog-title").inner_text()
                assert not page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"), (
                    f"Horizontal overflow at {width}px")
                assert not errors, errors
                page.add_style_tag(content=(
                    "body:after{content:'EXEMPLO DE TESTE — NÃO É A LOJA PUBLICADA';"
                    "position:fixed;top:0;right:0;background:#b91c1c;color:white;"
                    "z-index:99999;padding:5px 10px;font-size:11px;pointer-events:none}"))
                page.screenshot(path=str(ARTIFACTS / f"lovable-fixture-{width}x{height}.png"), full_page=True)
                if width == 1536:
                    page.locator(".chip").filter(has_text="Fotografias").click()
                    assert page.locator(".app-card").count() == 1
                    assert "Immich" in page.locator(".app-card").first.inner_text()
                    assert page.locator("#catalog-tools").is_visible()
                    page.locator("#search").fill("sem-correspondencia-zz")
                    assert page.locator(".app-card").count() == 0
                    page.locator("#search").fill("")
                    assert page.locator(".app-card").count() == 1
                    page.locator(".chip").filter(has_text="Todas").click()
                    assert page.locator(".app-card").count() == 4
                    page.locator(".details-button").first.click()
                    assert page.locator("#details").is_visible()
                    assert "não instala contentores" in page.locator(".detail-disclaimer").inner_text()
                    page.locator("#details-close").click()
                    assert not page.locator("#details").is_visible()
                    page.locator("#show-all").click()
                    assert page.locator("#catalog-tools").is_hidden()
                    assert page.locator(".app-card").count() == 4
                    page.locator("#show-install-guide").click()
                    assert page.locator("#como-instalar").is_visible()
                    assert not errors, errors
                page.close()
            browser.close()
        print("Chromium verified: 1536x864 / 390x844 screenshots and working UI controls")
    finally:
        server.shutdown()
