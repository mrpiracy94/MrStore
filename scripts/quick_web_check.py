#!/usr/bin/env python3
"""Fast, isolated MrStore storefront checks. Never modifies the published catalog.

Usage:
    pip install playwright
    playwright install chromium
    python scripts/quick_web_check.py
Outputs: out/web-fast/*.png and result.json
"""
import json
import pathlib
import shutil
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "web-fast"
FIXTURE = [
    {"id": "plex", "name": "Plex", "category": "Media", "tagline": "Biblioteca de vídeo"},
    {"id": "immich", "name": "Immich", "category": "Graphics", "tagline": "Fotografias privadas"},
    {"id": "nextcloud", "name": "Nextcloud", "category": "Cloud", "tagline": "Ficheiros na nuvem"},
    {"id": "jellyfin", "name": "Jellyfin", "category": "Media", "tagline": "Séries e filmes"},
]


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Missing Playwright: pip install playwright && playwright install chromium")
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="mrstore-fast-") as tmp:
        site = pathlib.Path(tmp)
        shutil.copy(ROOT / "web" / "index.html", site / "index.html")
        shutil.copytree(ROOT / "web", site / "web", dirs_exist_ok=True)
        branding = ROOT / "assets" / "branding"
        if branding.exists():
            shutil.copytree(branding, site / "assets" / "branding", dirs_exist_ok=True)
        (site / "index.json").write_text(
            json.dumps({"version": 2, "apps": FIXTURE}), encoding="utf-8"
        )

        class QuietHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(site), **kwargs)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                for width, height in [(1536, 864), (390, 844)]:
                    page = browser.new_page(viewport={"width": width, "height": height},
                                            device_scale_factor=1)
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(f"http://127.0.0.1:{server.server_port}/",
                              wait_until="networkidle", timeout=20000)
                    assert page.locator(".showcase").is_visible(), "Hero missing"
                    assert page.locator(".category-tile").count() == 8, "Category tiles != 8"
                    assert page.locator(".card").count() == 4, "Catalog did not render"
                    assert not errors, f"JavaScript errors: {errors}"
                    assert not page.evaluate(
                        "document.documentElement.scrollWidth > window.innerWidth + 1"
                    ), f"Horizontal overflow at {width}px"
                    # Check filtering and reset on the actual rendered DOM.
                    page.locator("#search").fill("immich")
                    assert page.locator(".card").count() == 1, "Search not filtering"
                    page.locator("#show-all").click()
                    assert page.locator(".card").count() == 4, "Reset failed"
                    page.locator("#sort").select_option("reverse")
                    names = page.locator(".card h3").all_inner_texts()
                    assert names == sorted(names, reverse=True, key=str.casefold), (
                        f"Reverse ordering incorrect: {names}"
                    )
                    page.locator("#sort").select_option("name")
                    page.locator(".category-tile").nth(1).click()
                    assert page.locator(".card").count() == 2, "Media tile filtering failed"
                    page.locator(".category-tile").first.click()
                    assert page.locator(".card").count() == 4, "All tile failed"
                    # Screenshot without browser test interactions changing the reference.
                    page.evaluate("window.scrollTo(0,0)")
                    image = OUT / f"storefront-{width}.png"
                    page.screenshot(path=str(image), full_page=True)
                    results.append({"viewport": f"{width}x{height}",
                                    "cards": 4, "screenshot": str(image.relative_to(ROOT)),
                                    "status": "PASS"})
                    print(f"PASS {width}x{height}: 4 cards, search, sort, filters, no overflow")
                    page.close()
                browser.close()
        finally:
            server.shutdown()
    (OUT / "result.json").write_text(
        json.dumps({"fixture": True, "results": results}, indent=2), encoding="utf-8"
    )
    print("PASS fast storefront checks (TEST FIXTURE, not production catalog).")


if __name__ == "__main__":
    main()
