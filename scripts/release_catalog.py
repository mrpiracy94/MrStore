"""Fail-closed per-app release selection with strict 8-shard Trivy evidence.

No source app is removed from git; unsafe or inconclusive apps are quarantined.
Every published service image is rewritten to the exact image digest scanned.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import shutil
import yaml

from catalog import ROOT, apps, image_usage
from cves import shard_images
from curate_taglines import load_summaries, render_manifest
from release_scan import image_platforms
from privilege_policy import risky_settings
from image_freshness import RETIRED_UPSTREAM

HEX = re.compile(r"^[a-f0-9]{64}$")
# Required Compose interpolation is resolved before ZimaOS can show service
# x-casaos.envs: the official store v2 builder strips that service metadata.
# Do not mistake an unresolved secret for a usable or safe install.
REQUIRED_COMPOSE_VARIABLE = re.compile(
    r"\$\{[A-Za-z_][A-Za-z0-9_]*(?::\?|\?)[^}]*\}"
)


def read_evidence(source_apps, report_dir: Path, shards: int = 8) -> dict:
    """Accept only exact full evidence from this image set and these shards."""
    usage = image_usage(source_apps)
    expected = set(usage)
    architectures = image_platforms(source_apps)
    discovered = {}
    for shard in range(shards):
        files = list(report_dir.rglob(f"release-cves-shard-{shard}.json"))
        if len(files) != 1:
            raise ValueError(f"Missing/duplicate security evidence for shard {shard}")
        data = json.loads(files[0].read_text(encoding="utf-8"))
        entries = data.get("results")
        if (data.get("shard") != shard or data.get("shards") != shards
                or data.get("images_total") != len(expected)
                or not isinstance(entries, list)
                or data.get("images_checked") != len(entries)):
            raise ValueError(f"Inconsistent security report: shard {shard}")
        expected_for_shard = set(shard_images(usage, shard, shards))
        names = [entry.get("image") for entry in entries if isinstance(entry, dict)]
        if len(names) != len(entries) or set(names) != expected_for_shard or len(set(names)) != len(names):
            raise ValueError(f"Unexpected/missing scanned images in shard {shard}")
        for entry in entries:
            image = entry["image"]
            if image in discovered:
                raise ValueError(f"Image scanned more than once: {image}")
            wanted_platforms = architectures[image]
            if entry.get("platforms") != wanted_platforms:
                raise ValueError(f"{image}: incomplete declared-platform coverage")
            pinned = entry.get("pinned")
            error = entry.get("error")
            if pinned is not None:
                if not isinstance(pinned, str) or "@sha256:" not in pinned:
                    raise ValueError(f"{image}: invalid pinned image")
                base, digest = pinned.rsplit("@sha256:", 1)
                if not HEX.fullmatch(digest) or base != image.split("@sha256:", 1)[0]:
                    raise ValueError(f"{image}: digest doesn't match source reference")
                if "@sha256:" in image and pinned != image:
                    raise ValueError(f"{image}: original immutable reference changed")
            scans = entry.get("scans")
            if not isinstance(scans, dict):
                raise ValueError(f"{image}: missing scan records")
            if scans and set(scans) != set(wanted_platforms):
                raise ValueError(f"{image}: partial architecture scan")
            safe = pinned is not None and not error and set(scans) == set(wanted_platforms)
            for value in scans.values():
                if not isinstance(value, dict):
                    raise ValueError(f"{image}: malformed per-arch scan")
                high, critical = value.get("high"), value.get("critical")
                if type(high) is not int or type(critical) is not int or high < 0 or critical < 0:
                    raise ValueError(f"{image}: invalid CVE counts")
                if value.get("status") not in ("ok", "error"):
                    raise ValueError(f"{image}: invalid scan status")
                if value.get("status") == "error" or value.get("error") or high or critical:
                    safe = False
            reported = entry.get("status")
            calculated = ("error" if error or not pinned or
                          any(v.get("status") == "error" for v in scans.values())
                          else "vulnerable" if any(v["high"] or v["critical"] for v in scans.values())
                          else "clean")
            if reported != calculated:
                raise ValueError(f"{image}: dishonest status in scan report")
            if reported != "clean":
                safe = False
            discovered[image] = {"safe": bool(safe), "pinned": pinned, "status": reported}
    if set(discovered) != expected:
        raise ValueError("Release coverage incomplete or inconsistent")
    return discovered


def insecure_defaults(app) -> list[str]:
    """Conservative rule: unresolved dangerous defaults are never released."""
    # The final release selector applies the same privilege policy as PR review,
    # even to legacy configurations that predate the regression baseline.
    flags = [f"{service}: dangerous {code}={detail}"
             for service, code, detail in sorted(risky_settings(app.source))]
    # Docker Compose also interpolates top-level network/volume/config values.
    # Exclude service definitions checked below and descriptive x-* metadata.
    root_runtime = {key: value for key, value in app.source.items()
                    if key != "services" and not str(key).startswith("x-")}
    root_json = json.dumps(root_runtime)
    if "CHANGE_ME" in root_json:
        flags.append("compose: default credentials not configured")
    if REQUIRED_COMPOSE_VARIABLE.search(root_json):
        flags.append("compose: required Compose installation variables unsupported by verified ZimaOS v2 installer")
    for service, spec in (app.source.get("services") or {}).items():
        if not isinstance(spec, dict):
            flags.append(f"{service}: invalid service spec")
            continue
        if spec.get("userns") == "host":
            flags.append(f"{service}: unsafe userns=host")
        # Retain the independent upstream-retirement gate merged via PR #70.
        # No amount of successful Trivy evidence makes a retired image viable.
        image_ref = spec.get("image")
        if image_ref in RETIRED_UPSTREAM:
            flags.append(f"{service}: discontinued upstream image {image_ref}; "
                         f"see {RETIRED_UPSTREAM[image_ref]}")
        env = spec.get("environment") or []
        # Detect unsafe placeholders across actual Compose service fields,
        # while ignoring purely descriptive x-casaos installer metadata.
        runtime_spec = {key: value for key, value in spec.items()
                        if not str(key).startswith("x-")}
        runtime_json = json.dumps(runtime_spec)
        if "CHANGE_ME" in runtime_json:
            flags.append(f"{service}: default credentials not configured")
        # ${VAR:?message} and ${VAR?message} both require host-side values;
        # the verified ZimaOS v2 installer does not expose a reliable prompt.
        # Never publish a service that would fail Compose interpolation.
        if REQUIRED_COMPOSE_VARIABLE.search(runtime_json):
            flags.append(f"{service}: required Compose installation variables unsupported by verified ZimaOS v2 installer")
        pairs = (env.items() if isinstance(env, dict) else
                 (value.split("=", 1) for value in env
                  if isinstance(value, str) and "=" in value))
        for key, value in pairs:
            if str(key) in {"HOMEPAGE_ALLOWED_HOSTS", "ALLOWED_HOSTS", "ALLOWED_HOST"} and str(value).strip() == "*":
                flags.append(f"{service}: wildcard host header validation disabled")
    return sorted(set(flags))


def stage(source: Path, evidence: dict, destination: Path, summaries: dict) -> dict:
    if destination.exists():
        raise ValueError("Refusing to overwrite existing staging directory")
    source_apps = apps(source)
    approved = {}
    quarantine = {}
    for app in source_apps:
        reasons = insecure_defaults(app)
        locked = {}
        for service, spec in app.source["services"].items():
            image = spec["image"]
            item = evidence[image]
            if not item["safe"]:
                reasons.append(f"{service}: {image}: {item['status']}")
            else:
                locked[service] = item["pinned"]
        if reasons:
            quarantine[app.folder] = sorted(set(reasons))
        else:
            approved[app.folder] = (app, locked)
    result = {
        "source_apps": len(source_apps), "approved_count": len(approved),
        "quarantined_count": len(quarantine),
        "approved": sorted(approved), "quarantined": quarantine,
        "policy": "all images scanned clean on declared platforms, pinned digest, safe static defaults",
    }
    if not approved:
        return result
    destination.mkdir(parents=True)
    (destination / "Apps").mkdir()
    for filename in ("store-config.json", "supported-languages.json"):
        shutil.copyfile(source / filename, destination / filename)
    category = json.loads((source / "category-list.json").read_text(encoding="utf-8"))
    counts = Counter(app.metadata.get("category") for app, _ in approved.values())
    for entry in category:
        entry["count"] = counts.get(entry["name"], 0)
    (destination / "category-list.json").write_text(json.dumps(category, indent=2) + "\n")
    recommendations = json.loads((source / "recommend-list.json").read_text(encoding="utf-8"))
    recommendations = [item for item in recommendations if item.get("name") in approved]
    (destination / "recommend-list.json").write_text(json.dumps(recommendations, indent=2) + "\n")
    for folder, (app, locked) in approved.items():
        target = destination / "Apps" / folder
        shutil.copytree(app.path.parent, target)
        # Curate before changing images: its checker proves no service edits.
        text = render_manifest(app.path.read_text(encoding="utf-8"), folder, summaries[folder])
        manifest = yaml.safe_load(text)
        for service, image in locked.items():
            manifest["services"][service]["image"] = image
        (target / "docker-compose.yml").write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
        # Verify all references are pinned and no service was omitted.
        out = yaml.safe_load((target / "docker-compose.yml").read_text(encoding="utf-8"))
        if {name: x["image"] for name, x in out["services"].items()} != locked:
            raise ValueError(f"{folder}: staged compose differs from clean image set")
    return result


def verify_published(dist: Path, selected: dict, staged: Path | None = None) -> None:
    index = json.loads((dist / "index.json").read_text(encoding="utf-8"))
    published = index.get("apps", [])
    if len(published) != selected["approved_count"]:
        raise ValueError("Published count differs from approved release")
    want = {"io.github.mrpiracy94." + folder for folder in selected["approved"]}
    actual = {item["id"] for item in published}
    if actual != want or len(actual) != len(published):
        raise ValueError("Unsafe/omitted/duplicate application in published index")
    for app_id in actual:
        compose = dist / "apps" / app_id / "docker-compose.yml"
        content = yaml.safe_load(compose.read_text(encoding="utf-8"))
        images = {key: spec.get("image") for key, spec in content["services"].items()}
        if any(not isinstance(image, str) or "@sha256:" not in image
               for image in images.values()):
            raise ValueError(f"{app_id}: published container not immutable")
        if staged is not None:
            folder = app_id.removeprefix("io.github.mrpiracy94.")
            intended = yaml.safe_load((staged / "Apps" / folder /
                                      "docker-compose.yml").read_text(encoding="utf-8"))
            expected_images = {name: spec["image"] for name, spec in intended["services"].items()}
            if images != expected_images:
                raise ValueError(f"{app_id}: published images differ from approved scanned digests")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--reports", type=Path, required=True)
    p.add_argument("--source", type=Path, default=ROOT)
    p.add_argument("--stage", type=Path, default=ROOT / "release-source")
    p.add_argument("--report", type=Path, default=ROOT / "out/release-selection.json")
    opts = p.parse_args()
    evidence = read_evidence(apps(opts.source), opts.reports)
    result = stage(opts.source, evidence, opts.stage, load_summaries())
    opts.report.parent.mkdir(parents=True, exist_ok=True)
    opts.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Approved {result['approved_count']}/{result['source_apps']} apps. "
          f"Quarantined {result['quarantined_count']} with recorded reasons.")
    if not result["approved_count"]:
        raise SystemExit("No clean app can be published: previous release NOT replaced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
