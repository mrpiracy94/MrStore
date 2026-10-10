"""Catalog-wide ZimaOS device-test evidence inventory (never runs containers).

Records represent human-reported tests backed by an issue/PR. They are not
independent certification and become stale when their Compose file changes.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from catalog import ROOT, apps

LEVELS = {"C2": 2, "C3": 3, "C4": 4}
REQUIRED_CHECKS = {
    "C2": {"runtime_observed", "ui_or_service_checked"},
    "C3": {"installed_from_mrstore", "core_function_checked", "restart_persistence_checked"},
    "C4": {"backup_checked", "upgrade_checked", "restore_checked", "rollback_checked"},
}
CHECK_NAMES = set().union(*REQUIRED_CHECKS.values())
EVIDENCE = re.compile(r"https://github\.com/mrpiracy94/MrStore/(?:issues|pull)/[1-9][0-9]*(?:#[A-Za-z0-9_-]+)?$")
HEX_SHA = re.compile(r"[0-9a-f]{64}$")
IMAGE_REF = re.compile(r"[A-Za-z0-9._/@:-]{3,200}$")
RECORD_FIELDS = {"app", "architecture", "zimaos_version", "tested_at", "compose_sha256",
                 "image_ref", "level", "evidence_url", "checks"}


def validate_record(item: dict, by_name: dict, index: int) -> None:
    prefix = f"tests[{index}]"
    if not isinstance(item, dict) or set(item) != RECORD_FIELDS:
        raise ValueError(f"{prefix}: fields must be exactly {sorted(RECORD_FIELDS)}")
    name = item["app"]
    if not isinstance(name, str) or name not in by_name:
        raise ValueError(f"{prefix}: unknown catalog app")
    app = by_name[name]
    if not isinstance(item["architecture"], str) or item["architecture"] not in (app.metadata.get("architectures") or []):
        raise ValueError(f"{prefix}: architecture not declared for app")
    if not isinstance(item["level"], str) or item["level"] not in LEVELS:
        raise ValueError(f"{prefix}: level must be C2, C3 or C4")
    if (not isinstance(item["zimaos_version"], str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+ -]{0,79}", item["zimaos_version"])):
        raise ValueError(f"{prefix}: invalid ZimaOS version")
    try:
        tested = date.fromisoformat(item["tested_at"])
    except (TypeError, ValueError):
        raise ValueError(f"{prefix}: invalid test date (YYYY-MM-DD)") from None
    if tested.isoformat() != item["tested_at"] or tested > date.today():
        raise ValueError(f"{prefix}: future or noncanonical test date")
    if not isinstance(item["compose_sha256"], str) or not HEX_SHA.fullmatch(item["compose_sha256"]):
        raise ValueError(f"{prefix}: compose_sha256 must be a 64-char lowercase SHA-256")
    if not isinstance(item["image_ref"], str) or not IMAGE_REF.fullmatch(item["image_ref"]):
        raise ValueError(f"{prefix}: invalid image reference (never include credentials)")
    if not isinstance(item["evidence_url"], str) or not EVIDENCE.fullmatch(item["evidence_url"]):
        raise ValueError(f"{prefix}: evidence must link to a MrStore GitHub issue/PR")
    checks = item["checks"]
    if not isinstance(checks, dict) or set(checks) != CHECK_NAMES:
        raise ValueError(f"{prefix}: checks must contain exactly {sorted(CHECK_NAMES)}")
    if any(type(value) is not bool for value in checks.values()):
        raise ValueError(f"{prefix}: checks must be booleans")
    required = set().union(*(REQUIRED_CHECKS[level] for level in LEVELS
                             if LEVELS[level] <= LEVELS[item["level"]]))
    if any(checks[step] is not True for step in required):
        raise ValueError(f"{prefix}: level {item['level']} lacks required checks")


def inventory(root: Path = ROOT, registry_path: Path | None = None) -> dict:
    root = Path(root)
    catalog = apps(root)
    by_name = {app.folder: app for app in catalog}
    source = registry_path or root / "data/zimaos-device-tests.json"
    registry = json.loads(source.read_text(encoding="utf-8"))
    if (not isinstance(registry, dict) or set(registry) != {"schema", "tests"}
            or type(registry["schema"]) is not int or registry["schema"] != 1
            or not isinstance(registry["tests"], list)):
        raise ValueError("Device tests registry must have schema: 1 and tests: []")

    current_digests = {app.folder: sha256(app.path.read_bytes()).hexdigest() for app in catalog}
    grouped = defaultdict(lambda: defaultdict(list))
    stale_records = 0
    for index, record in enumerate(registry["tests"]):
        validate_record(record, by_name, index)
        if record["compose_sha256"] != current_digests[record["app"]]:
            stale_records += 1
        else:
            grouped[record["app"]][record["architecture"]].append(record)

    entries = []
    for app in catalog:
        declared = sorted(app.metadata.get("architectures") or [])
        levels, evidence = {}, {}
        for arch in declared:
            candidates = grouped[app.folder][arch]
            best = max(candidates, key=lambda r: (LEVELS[r["level"]], r["tested_at"]),
                       default=None)
            levels[arch] = best["level"] if best else None
            evidence[arch] = best["evidence_url"] if best else None
        ranks = [LEVELS[level] if level else 0 for level in levels.values()]
        entries.append({
            "app": app.folder,
            "declared_architectures": declared,
            "compose_sha256": current_digests[app.folder],
            "levels_by_architecture": levels,
            "evidence_by_architecture": evidence,
            "with_device_evidence": any(ranks),
            "c3_any_architecture": any(rank >= 3 for rank in ranks),
            "c3_all_architectures": bool(ranks) and all(rank >= 3 for rank in ranks),
            "c4_all_architectures": bool(ranks) and all(rank >= 4 for rank in ranks),
        })

    return {
        "schema": 1,
        "method": "human_reported_evidence_not_independently_certified",
        "total_apps": len(entries),
        "recorded_tests": len(registry["tests"]),
        "stale_records": stale_records,
        "apps_with_current_device_evidence": sum(x["with_device_evidence"] for x in entries),
        "apps_without_current_device_evidence": sum(not x["with_device_evidence"] for x in entries),
        "c3_any_architecture": sum(x["c3_any_architecture"] for x in entries),
        "c3_all_declared_architectures": sum(x["c3_all_architectures"] for x in entries),
        "c4_all_declared_architectures": sum(x["c4_all_architectures"] for x in entries),
        "apps": entries,
    }


def markdown(data: dict) -> str:
    lines = [
        "# MrStore — cobertura de testes reais no ZimaOS", "",
        "**Registos declarados por pessoas com evidência num issue/PR, não certificados automaticamente.**",
        "A validação estática, os scans de CVEs e os smoke tests não preenchem esta tabela.",
        "", f"- Aplicações no catálogo de origem: **{data['total_apps']}**",
        f"- Com prova de dispositivo ainda atual: **{data['apps_with_current_device_evidence']}**",
        f"- Sem prova atual registada: **{data['apps_without_current_device_evidence']}**",
        f"- C3 numa arquitetura pelo menos: **{data['c3_any_architecture']}**",
        f"- C3 em todas as arquiteturas declaradas: **{data['c3_all_declared_architectures']}**",
        f"- C4 em todas as arquiteturas declaradas: **{data['c4_all_declared_architectures']}**",
        f"- Registos históricos desatualizados por alteração do Compose: **{data['stale_records']}**",
        "", "| Aplicação | Arquitetura → nível atual | Evidência |",
        "| --- | --- | --- |",
    ]
    for item in data["apps"]:
        arch = ", ".join(f"{name}: {level or 'sem registo'}"
                         for name, level in item["levels_by_architecture"].items())
        links = ", ".join(f"[{name}]({url})"
                          for name, url in item["evidence_by_architecture"].items() if url)
        lines.append(f"| {item['app']} | {arch} | {links or '—'} |")
    lines += ["", "A ausência de registo não significa que a aplicação falha ou que nunca foi testada.",
              "Para registar um teste, consultar docs/ZIMAOS_COMPATIBILITY.md.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--md", type=Path)
    args = parser.parse_args()
    data = inventory(args.root, args.registry)
    outputs = ((args.json or args.root / "out/zimaos-coverage.json",
                json.dumps(data, indent=2, ensure_ascii=False) + "\n"),
               (args.md or args.root / "out/zimaos-coverage.md", markdown(data)))
    for target, content in outputs:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    print(f"ZimaOS documented: {data['apps_with_current_device_evidence']}/{data['total_apps']} "
          f"with any current evidence; C3 on every declared arch: "
          f"{data['c3_all_declared_architectures']}/{data['total_apps']}; "
          f"stale records: {data['stale_records']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
