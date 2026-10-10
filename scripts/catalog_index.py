"""Read-only catalog navigation and category/list integrity report.

Source of truth: Apps/*/docker-compose.yml (inert YAML). This never pulls,
installs, deploys or considers a static status to be ZimaOS runtime proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import unicodedata

from catalog import ROOT, apps
from compatibility import inspect_app


def normalized(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).casefold()
    return "".join(char for char in text if not unicodedata.combining(char))


def localized(value: object) -> str:
    if isinstance(value, dict):
        for language in ("pt_PT", "en_US"):
            text = value.get(language)
            if isinstance(text, str) and text.strip():
                return text.strip()
        return ""
    return value.strip() if isinstance(value, str) else ""


def records_from_apps(source_apps) -> list[dict]:
    records = []
    for app in source_apps:
        meta = app.metadata
        category = meta.get("category")
        services = app.source.get("services") or {}
        if not isinstance(services, dict):
            services = {}
        arches = meta.get("architectures") or []
        if not isinstance(arches, list):
            arches = []
        records.append({
            "slug": app.folder,
            "id": app.app_id,
            "title": localized(meta.get("title")) or app.folder,
            "category": category if isinstance(category, str) else "",
            "architectures": sorted(set(str(a) for a in arches)),
            "version": str(meta.get("version", "")),
            "ui": str(meta.get("port_map", "")) != "0",
            "service_count": len(services),
            "static_compatibility": inspect_app(app)["status"],
            "manifest": "Apps/" + app.folder + "/docker-compose.yml",
        })
    return sorted(records, key=lambda x: (normalized(x["category"]), normalized(x["title"]), x["slug"]))


def issue(level: str, code: str, message: str) -> dict:
    return {"level": level, "code": code, "message": message}


def check_lists(records: list[dict], categories: object,
                recommendations: object, featured: object | None = None) -> list[dict]:
    findings = []
    slugs = [r["slug"] for r in records]
    if len(set(slugs)) != len(slugs):
        findings.append(issue("error", "duplicate_app", "Duplicate application slugs"))
    if len({r["id"] for r in records}) != len(records):
        findings.append(issue("error", "duplicate_id", "Duplicate catalog IDs"))
    by_slug = {r["slug"]: r for r in records}
    counts = Counter(r["category"] for r in records)
    if not isinstance(categories, list):
        return findings + [issue("error", "category_schema", "category-list.json must be a list")]
    declared = {}
    for idx, entry in enumerate(categories):
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not entry["name"]:
            findings.append(issue("error", "category_schema", "Invalid category row " + str(idx)))
            continue
        name = entry["name"]
        if name in declared:
            findings.append(issue("error", "category_duplicate", "Duplicate category: " + name))
            continue
        declared[name] = entry
        count = entry.get("count")
        if type(count) is not int or count < 0:
            findings.append(issue("error", "category_count_type", "Invalid category count: " + name))
        elif count != counts.get(name, 0):
            findings.append(issue("warning", "category_count_drift",
                                  name + ": declared " + str(count) + ", manifests " + str(counts.get(name, 0))))
    for name in sorted(set(counts) - set(declared)):
        findings.append(issue("warning", "category_not_listed",
                              "Manifest category is missing from category-list.json: " + name))
    for name in sorted(set(declared) - set(counts)):
        findings.append(issue("warning", "category_unused",
                              "Configured category has no matching manifests: " + name))

    if not isinstance(recommendations, list):
        findings.append(issue("error", "recommendation_schema", "recommend-list.json must be a list"))
    else:
        seen_slugs, seen_ids = set(), set()
        for idx, rec in enumerate(recommendations):
            if not isinstance(rec, dict):
                findings.append(issue("error", "recommendation_schema", "Invalid recommendation row " + str(idx)))
                continue
            slug = rec.get("name")
            ident = rec.get("id")
            if not isinstance(slug, str) or not slug:
                findings.append(issue("error", "recommendation_schema", "Missing recommendation slug"))
                continue
            if slug in seen_slugs:
                findings.append(issue("error", "recommendation_duplicate", "Duplicate recommendation: " + slug))
            seen_slugs.add(slug)
            if type(ident) is not int or ident in seen_ids or ident <= 0:
                findings.append(issue("error", "recommendation_id", "Invalid or duplicated recommendation ID"))
            seen_ids.add(ident)
            if slug not in by_slug:
                findings.append(issue("error", "recommendation_missing", "Unknown recommendation: " + slug))
    if featured is not None:
        if not isinstance(featured, list):
            findings.append(issue("error", "featured_schema", "featured-apps.json must be a list"))
        else:
            seen = set()
            for rec in featured:
                slug = rec.get("appid") if isinstance(rec, dict) else None
                if not isinstance(slug, str) or not slug:
                    findings.append(issue("error", "featured_schema", "Featured entry needs appid"))
                    continue
                if slug in seen:
                    findings.append(issue("error", "featured_duplicate", "Duplicate featured app: " + slug))
                seen.add(slug)
                if slug not in by_slug:
                    findings.append(issue("error", "featured_missing", "Unknown featured app: " + slug))
    return sorted(findings, key=lambda x: (x["level"], x["code"], x["message"]))


def filter_records(records: list[dict], *, category: str = "", query: str = "",
                   architecture: str = "") -> list[dict]:
    needle = normalized(query.strip())
    return [r for r in records
            if (not category or r["category"].casefold() == category.casefold())
            and (not architecture or architecture in r["architectures"])
            and (not needle or needle in normalized(r["title"] + " " + r["slug"] + " " + r["category"]))]


def create_index(source_apps, categories, recommendations, featured=None, *,
                 category: str = "", query: str = "", architecture: str = "") -> dict:
    records = records_from_apps(source_apps)
    findings = check_lists(records, categories, recommendations, featured)
    selected = filter_records(records, category=category, query=query, architecture=architecture)
    counts = Counter(r["category"] for r in records)
    return {
        "schema": 1,
        "method": "offline_source_manifest_inventory",
        "runtime_verified": False,
        "cve_scanned": False,
        "summary": {
            "total_apps": len(records),
            "selected_apps": len(selected),
            "categories_in_manifests": dict(sorted(counts.items())),
            "configured_categories": len(categories) if isinstance(categories, list) else 0,
            "recommendations": len(recommendations) if isinstance(recommendations, list) else 0,
            "featured": len(featured) if isinstance(featured, list) else 0,
            "errors": sum(x["level"] == "error" for x in findings),
            "warnings": sum(x["level"] == "warning" for x in findings),
        },
        "filters": {"category": category, "query": query, "architecture": architecture},
        "findings": findings,
        "apps": selected,
    }


def markdown(data: dict) -> str:
    summary = data["summary"]
    lines = [
        "# MrStore — índice navegável do catálogo",
        "",
        "**Inventário estático dos manifests de origem.** Não demonstra CVEs resolvidas, publicação",
        "aprovada ou instalação funcional no ZimaOS.",
        "",
        f"Aplicações: **{summary['total_apps']}** · Selecionadas: **{summary['selected_apps']}** · ",
        f"Categorias nos manifests: **{len(summary['categories_in_manifests'])}** · "
        f"Inconsistências: **{summary['errors']} erros / {summary['warnings']} avisos**.",
        "",
        "## Navegação por categoria",
        "",
        "| Categoria | Apps de origem |",
        "|---|---:|",
    ]
    for name, count in summary["categories_in_manifests"].items():
        lines.append(f"| {name} | {count} |")
    lines += ["", "## Aplicações", "",
              "| Aplicação | Categoria | Arquiteturas declaradas | Compatibilidade estática |",
              "|---|---|---|---|"]
    for item in data["apps"]:
        name = item["title"].replace("|", "/")
        lines.append(f"| [{name}](../{item['manifest']}) | {item['category']} | "
                     f"{', '.join(item['architectures'])} | {item['static_compatibility']} |")
    lines += ["", "## Consistência da organização", ""]
    if data["findings"]:
        for item in data["findings"]:
            lines.append(f"- **{item['level']}** `{item['code']}`: {item['message']}")
    else:
        lines.append("- Nenhuma discrepância de taxonomia/listas encontrada.")
    lines += ["", "O inventário apresenta todas as aplicações de origem, incluindo as que",
              "possam estar em quarentena no catálogo público. Nunca o tratar como lista",
              "de imagens aprovadas pelo scanner de segurança.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", type=Path, default=ROOT / "out/catalog-index.json")
    parser.add_argument("--markdown", type=Path, default=ROOT / "out/catalog-index.md")
    parser.add_argument("--category", default="")
    parser.add_argument("--search", default="")
    parser.add_argument("--architecture", choices=("amd64", "arm64"), default="")
    parser.add_argument("--strict-taxonomy", action="store_true",
                        help="Fail also on category/count drift; activate after taxonomy is aligned")
    args = parser.parse_args(argv)
    root = args.root
    categories = json.loads((root / "category-list.json").read_text(encoding="utf-8"))
    recommendations = json.loads((root / "recommend-list.json").read_text(encoding="utf-8"))
    feature_path = root / "featured-apps.json"
    featured = json.loads(feature_path.read_text(encoding="utf-8")) if feature_path.exists() else None
    data = create_index(apps(root), categories, recommendations, featured,
                        category=args.category, query=args.search,
                        architecture=args.architecture)
    for path, content in (
        (args.json, json.dumps(data, ensure_ascii=False, indent=2) + "\n"),
        (args.markdown, markdown(data)),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    info = data["summary"]
    print(f"Catalog index: {info['selected_apps']}/{info['total_apps']} apps; "
          f"{info['errors']} errors, {info['warnings']} taxonomy warnings")
    return 1 if info["errors"] or (args.strict_taxonomy and info["warnings"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
