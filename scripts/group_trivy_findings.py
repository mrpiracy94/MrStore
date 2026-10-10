"""Group HIGH/CRITICAL Trivy evidence across AMD64 and ARM64 releases.

Missing shards, errors and missing platforms remain explicit; never count as clean.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from catalog import apps, image_usage, ROOT
from release_scan import image_platforms

def aggregate(reports: list[dict], usage: dict[str,list[str]], expected: dict[str,list[str]]) -> dict:
    found = {}
    duplicate_images = []
    for report in reports:
        for entry in report.get("results", []):
            image = entry.get("image")
            if image in found:
                duplicate_images.append(image)
            found[image] = entry
    groups = defaultdict(lambda: {"apps":set(),"images":set(),"platforms":set(),"occurrences":[]})
    missing = sorted(set(expected) - set(found))
    unexpected = sorted(set(found) - set(expected))
    failures = []
    details = []
    for image in sorted(expected):
        entry = found.get(image)
        if not entry:
            continue
        issues = []
        for arch in expected[image]:
            scan = (entry.get("scans") or {}).get(arch)
            if not scan or scan.get("status") != "ok":
                issues.append({"platform":arch,"error":(scan or {}).get("error") or "missing platform scan"})
                continue
            hits = scan.get("findings")
            if not isinstance(hits, list):
                issues.append({"platform":arch,"error":"Trivy package detail evidence absent"})
                continue
            for hit in hits:
                if not isinstance(hit, dict) or hit.get("severity") not in ("HIGH","CRITICAL"):
                    continue
                package = hit.get("package") or "unknown"
                key = (package, hit.get("cve") or "unknown", hit.get("fixed") or "")
                item = groups[key]
                item["apps"].update(usage.get(image, []))
                item["images"].add(image)
                item["platforms"].add(arch)
                item["occurrences"].append({
                    "image":image, "platform":arch,"severity":hit["severity"],
                    "installed":hit.get("installed"),"target":hit.get("target")
                })
        if entry.get("error"):
            issues.append({"platform":"manifest","error":entry["error"]})
        if issues:
            failures.append({"image":image,"issues":issues,"apps":usage.get(image,[])})
        details.append({"image":image,"apps":usage.get(image,[]),"platforms":expected[image],
                        "status":"incomplete" if issues else entry.get("status","unknown"),
                        "critical":sum((entry.get("scans") or {}).get(a,{}).get("critical",0) for a in expected[image]),
                        "high":sum((entry.get("scans") or {}).get(a,{}).get("high",0) for a in expected[image])})
    categorized = []
    for (package,cve,fixed),data in groups.items():
        categorized.append({"package":package,"cve":cve,"fixed":fixed or None,
                            "apps":sorted(data["apps"]),"images":sorted(data["images"]),
                            "platforms":sorted(data["platforms"]),
                            "occurrences":sorted(data["occurrences"],key=lambda x:(x["image"],x["platform"]))})
    categorized.sort(key=lambda g:(-len(g["apps"]),-len(g["images"]),g["package"],g["cve"]))
    # One auditable state per app (not one state per shared image or per CVE).
    # A missing or incomplete scan takes precedence over a seemingly clean sibling image.
    by_image = {row["image"]: row for row in details}
    per_app = defaultdict(lambda: {
        "images": set(), "missing_images": set(), "incomplete_images": set(),
        "critical": 0, "high": 0,
    })
    for image in sorted(expected):
        row = by_image.get(image)
        for app in usage.get(image, []):
            item = per_app[app]
            item["images"].add(image)
            if row is None:
                item["missing_images"].add(image)
            elif row["status"] not in ("clean", "vulnerable"):
                item["incomplete_images"].add(image)
            else:
                item["critical"] += row["critical"]
                item["high"] += row["high"]
    applications = []
    for app, item in sorted(per_app.items(), key=lambda pair: pair[0].casefold()):
        if item["missing_images"] or item["incomplete_images"]:
            status = "not_verified"
        elif item["critical"] or item["high"]:
            status = "vulnerable"
        else:
            status = "no_high_critical_detected"
        applications.append({
            "app": app, "status": status, "critical": item["critical"], "high": item["high"],
            "images": sorted(item["images"]),
            "missing_images": sorted(item["missing_images"]),
            "incomplete_images": sorted(item["incomplete_images"]),
        })
    app_summary = {status: sum(item["status"] == status for item in applications)
                   for status in ("not_verified", "vulnerable", "no_high_critical_detected")}
    return {
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "expected_images":len(expected),"reported_images":len(found),
        "missing_images":missing,"unexpected_images":unexpected,
        "duplicate_images":sorted(set(duplicate_images)),
        "incomplete":failures,"groups":categorized,"images":details,
        "applications": applications, "applications_summary": app_summary,
        "critical":sum(e["critical"] for e in details),
        "high":sum(e["high"] for e in details)
    }

def markdown(report:dict)->str:
    lines = ["# Vulnerabilidades restantes — MrStore", "",
             "Trivy: HIGH/CRITICAL, imagens imutáveis, AMD64 e ARM64 conforme arquiteturas declaradas.",
             "Contagens representam ocorrências por imagem/arquitetura, não CVEs únicas nem aplicações únicas.",
             f"Imagens esperadas: {report['expected_images']}; presentes: {report['reported_images']}; "
             f"HIGH: {report['high']}; CRITICAL: {report['critical']}.", "",
             "## Evidência incompleta", ""]
    lines += [f"- {x['image']}: {', '.join(v['platform'] + ': ' + v['error'] for v in x['issues'])}"
              for x in report["incomplete"]]
    lines += [f"- imagem não analisada: {x}" for x in report["missing_images"]]
    lines += ["- Sem falhas conhecidas." ] if not report["incomplete"] and not report["missing_images"] else []
    lines += ["", "## Estado individual de cada aplicação", "",
              "NOT_VERIFIED = imagem, arquitetura ou evidência em falta. "
              "VULNERABLE = HIGH/CRITICAL encontrados. "
              "NO_HIGH_CRITICAL_DETECTED = análise completa sem HIGH/CRITICAL detetados (não é garantia absoluta).",
              "",
              "| Aplicação | Estado | CRITICAL | HIGH | Imagens |", "|---|---|---:|---:|---:|"]
    for app in report["applications"]:
        lines.append(f"| {app['app']} | {app['status'].upper()} | {app['critical']} | {app['high']} | {len(app['images'])} |")
    lines += ["", "### Totais por estado", ""]
    for status, count in report["applications_summary"].items():
        lines.append(f"- {status}: {count}")
    lines += ["","## Dependências partilhadas (por aplicações afetadas)",""]
    if not report["groups"]:
        lines.append("Sem HIGH/CRITICAL com detalhes disponíveis; confirmar se todos os scans foram completos.")
    for group in report["groups"]:
        lines += [f"### {group['package']} — {group['cve']}",
                  f"- Aplicações ({len(group['apps'])}): {', '.join(group['apps'])}",
                  f"- Imagens ({len(group['images'])}): {', '.join(group['images'])}",
                  f"- Arquiteturas: {', '.join(group['platforms'])}; versão corrigida: {group['fixed'] or 'não anunciada'}",
                  ""]
    return "\n".join(lines)+"\n"

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--reports",type=Path,required=True)
    p.add_argument("--json",type=Path,default=ROOT/"out/dualarch-groups.json")
    p.add_argument("--md",type=Path,default=ROOT/"out/dualarch-groups.md")
    args=p.parse_args()
    paths=sorted(args.reports.glob("**/release-cves-shard-*.json"))
    reports=[json.loads(path.read_text(encoding="utf-8")) for path in paths]
    catalog=apps()
    report=aggregate(reports,image_usage(catalog),image_platforms(catalog))
    report["shard_reports"]=len(paths)
    args.json.parent.mkdir(parents=True,exist_ok=True)
    args.json.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    args.md.write_text(markdown(report),encoding="utf-8")
    print(f"{len(report['groups'])} package/CVE groups, {len(report['incomplete'])} inconclusive, "
          f"{len(report['missing_images'])} missing images; {len(paths)} shards",flush=True)
    return 2 if len(paths)!=8 or report["missing_images"] or report["duplicate_images"] or report["incomplete"] else 0

if __name__=="__main__":
    raise SystemExit(main())
