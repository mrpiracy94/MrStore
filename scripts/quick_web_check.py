#!/usr/bin/env python3
"""Fast, isolated MrStore storefront checks. Never modifies the published catalog.

Usage:
    pip install playwright
    python -m playwright install chromium
    python scripts/quick_web_check.py
Outputs: out/web-fast/*.png and result.json, including failed checks.
The fixture checks interface behavior, not the production catalog or Docker security.
"""
import json
import pathlib
import shutil
import sys
import tempfile
import threading
import time
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "web-fast"
VIEWPORTS = [(1536, 864), (768, 1024), (390, 844), (360, 800)]
FIXTURE = [
    {"id": "plex", "name": "Plex", "category": "Media", "tagline": "Biblioteca de vídeo"},
    {"id": "immich", "name": "Immich", "category": "Graphics", "tagline": "Fotografias privadas"},
    {"id": "nextcloud", "name": "Nextcloud", "category": "Cloud", "tagline": "Ficheiros na nuvem"},
    {"id": "jellyfin", "name": "Jellyfin", "category": "Media", "tagline": "Séries e filmes"},
]


def require(condition, message):
    # Keep checks enabled even when Python is run with -O.
    if not condition:
        raise AssertionError(message)


def check_viewport(browser, expect, url, width, height):
    result = {"viewport": f"{width}x{height}", "status": "FAIL", "checks": []}
    errors = []
    page = browser.new_page(
        viewport={"width": width, "height": height}, device_scale_factor=1,
        is_mobile=width <= 700, has_touch=width <= 700,
    )
    page.set_default_timeout(5000)
    page.on("pageerror", lambda error: errors.append(f"JavaScript: {error}"))
    page.on("console", lambda msg: errors.append(f"Console: {msg.text}")
            if msg.type == "error" else None)
    page.on("response", lambda response: errors.append(
        f"HTTP {response.status}: {response.url}") if response.status >= 400 else None)
    page.on("requestfailed", lambda request: errors.append(
        f"Request: {request.url}: {request.failure}"))
    stage = "load"
    try:
        page.goto(url, wait_until="networkidle", timeout=20000)
        expect(page.locator(".showcase")).to_be_visible()
        expect(page.locator(".category-tile")).to_have_count(8)
        expect(page.locator(".card")).to_have_count(len(FIXTURE))
        result["checks"].append(stage)

        stage = "layout"
        layout = page.evaluate("""() => {
            const hero = document.querySelector('.showcase').getBoundingClientRect();
            const clipped = [];
            for (const el of document.querySelectorAll(
                '.showcase-brand, .showcase h1, .showcase p, .benefits b, .benefits small')) {
                const range = document.createRange();
                range.selectNodeContents(el);
                if ([...range.getClientRects()].some(r =>
                    r.left < hero.left - 1 || r.right > hero.right + 1 ||
                    r.top < hero.top - 1 || r.bottom > hero.bottom + 1)) {
                    clipped.push(el.textContent.trim());
                }
            }
            return {
                overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
                clippedHeroText: clipped,
            };
        }""")
        result["layout"] = layout
        require(not layout["overflow"], f"Horizontal overflow at {width}px")
        require(not layout["clippedHeroText"], f"Clipped hero text: {layout['clippedHeroText']}")
        result["checks"].append(stage)

        stage = "search_and_reset"
        page.locator("#search").fill("immich")
        expect(page.locator(".card h3")).to_have_text(["Immich"])
        page.locator("#show-all").click()
        expect(page.locator("#search")).to_have_value("")
        expect(page.locator(".card")).to_have_count(len(FIXTURE))
        result["checks"].append(stage)

        stage = "empty_state_and_reset"
        page.locator("#search").fill("no-such-fixture-app")
        expect(page.locator(".card")).to_have_count(0)
        expect(page.locator(".empty-state")).to_be_visible()
        page.locator(".empty-state button").click()
        expect(page.locator("#search")).to_have_value("")
        expect(page.locator(".card")).to_have_count(len(FIXTURE))
        result["checks"].append(stage)

        stage = "sorting"
        for option, names in [
            ("reverse", ["Plex", "Nextcloud", "Jellyfin", "Immich"]),
            ("category", ["Nextcloud", "Immich", "Jellyfin", "Plex"]),
            ("name", ["Immich", "Jellyfin", "Nextcloud", "Plex"]),
        ]:
            page.locator("#sort").select_option(option)
            expect(page.locator(".card h3")).to_have_text(names)
        result["checks"].append(stage)

        stage = "category_filters"
        for tile, names in [(1, ["Jellyfin", "Plex"]), (2, ["Immich"]),
                            (3, ["Nextcloud"]), (6, [])]:
            page.locator(".category-tile").nth(tile).click()
            expect(page.locator(".card h3")).to_have_text(names)
            expect(page.locator(".category-tile").nth(tile)).to_have_class("category-tile active")
        expect(page.locator(".empty-state")).to_be_visible()
        page.locator(".category-tile").first.click()
        expect(page.locator(".card")).to_have_count(len(FIXTURE))
        result["checks"].append(stage)

        stage = "runtime_errors"
        # Let the final render finish before checking errors from all interactions.
        page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        require(not errors, f"Browser errors: {errors}")
        result["checks"].append(stage)
        result["cards"] = page.locator(".card").count()
        result["status"] = "PASS"
    except Exception as error:
        result["failed_check"] = stage
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        # Capture the failing page too, and keep testing the other viewports.
        try:
            page.evaluate("window.scrollTo(0,0)")
            screenshot = OUT / f"storefront-{width}.png"
            page.screenshot(path=str(screenshot), full_page=True, animations="disabled")
            result["screenshot"] = str(screenshot.relative_to(ROOT))
        except Exception as error:
            result["status"] = "FAIL"
            result["screenshot_error"] = str(error)
        if errors:
            result["status"] = "FAIL"
            result["browser_errors"] = errors
        page.close()
    print(f"{result['status']} {width}x{height}: {result.get('error', ', '.join(result['checks']))}")
    return result


def run_checks(report):
    from playwright.sync_api import expect, sync_playwright

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
                try:
                    for width, height in VIEWPORTS:
                        report["results"].append(check_viewport(
                            browser, expect, f"http://127.0.0.1:{server.server_port}/", width, height
                        ))
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"fixture": True, "status": "FAIL", "results": []}
    started = time.monotonic()
    try:
        # Avoid uploading stale screenshots from an earlier successful execution.
        for old in OUT.glob("storefront-*.png"):
            old.unlink()
        run_checks(report)
        if len(report["results"]) == len(VIEWPORTS) and all(
            item["status"] == "PASS" for item in report["results"]
        ):
            report["status"] = "PASS"
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        traceback.print_exc()
    finally:
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        (OUT / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"{report['status']} fast storefront checks (TEST FIXTURE, not production catalog).")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
