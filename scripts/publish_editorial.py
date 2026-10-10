"""Publish the editorial catalog without claiming third-party images are certified."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
from catalog import ROOT, apps
from featured import load_featured
from curate_taglines import load_summaries, render_manifest
from release_catalog import insecure_defaults

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--featured", type=Path, default=ROOT / "data/featured-apps.json")
    p.add_argument("--stage", type=Path, default=ROOT / "release-source")
    p.add_argument("--report", type=Path, default=ROOT / "out/release-selection.json")
    opts = p.parse_args()
    source = apps(ROOT)
    featured = set(load_featured(opts.featured, {app.folder for app in source}))
    if opts.stage.exists():
        raise SystemExit("Staging directory already exists")
    opts.stage.mkdir(parents=True)
    (opts.stage / "Apps").mkdir()
    for name in ("store-config.json", "supported-languages.json"):
        shutil.copyfile(ROOT / name, opts.stage / name)
    selected = [app for app in source if app.folder in featured]
    summaries = load_summaries()
    warnings = {}
    for app in selected:
        target = opts.stage / "Apps" / app.folder
        shutil.copytree(app.path.parent, target)
        manifest = target / "docker-compose.yml"
        manifest.write_text(render_manifest(app.path.read_text(encoding="utf-8"), app.folder, summaries[app.folder]), encoding="utf-8")
        issues = insecure_defaults(app)
        if issues:
            warnings[app.folder] = issues
    category = json.loads((ROOT / "category-list.json").read_text(encoding="utf-8"))
    counts = Counter(app.metadata.get("category") for app in selected)
    for entry in category:
        entry["count"] = counts.get(entry["name"], 0)
    (opts.stage / "category-list.json").write_text(json.dumps(category, indent=2) + "\n", encoding="utf-8")
    recommendations = json.loads((ROOT / "recommend-list.json").read_text(encoding="utf-8"))
    recommendations = [item for item in recommendations if item.get("name") in featured]
    (opts.stage / "recommend-list.json").write_text(json.dumps(recommendations, indent=2) + "\n", encoding="utf-8")
    result = {"source_apps": len(source), "featured_count": len(featured),
              "approved_count": len(selected), "approved": sorted(featured),
              "quarantined_count": 0, "quarantined": {},
              "deferred_count": len(source) - len(selected),
              "deferred": sorted({app.folder for app in source} - featured),
              "warnings": warnings, "certification": "not_assessed",
              "policy": "Editorial listing only; upstream images are not certified by MrStore"}
    opts.report.parent.mkdir(parents=True, exist_ok=True)
    opts.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Staged {len(selected)} editorial apps without certification claims")
    if len(selected) != 96:
        raise SystemExit("Expected exactly 96 editorial apps")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
