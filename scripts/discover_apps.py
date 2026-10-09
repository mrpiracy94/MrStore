#!/usr/bin/env python3
"""Create review-only issues for curated missing apps, never auto-install or merge."""
import json
from pathlib import Path
import re
import subprocess
from catalog import ROOT, apps

SLUG = re.compile(r"^[a-z][a-z0-9-]{1,50}$")


def missing_candidates(root: Path = ROOT) -> list[dict]:
    proposals = json.loads((root / "data/app-candidates.json").read_text(encoding="utf-8"))
    existing = {item.folder for item in apps(root)}
    seen = set()
    pending = []
    for candidate in proposals:
        slug = candidate["slug"]
        if not SLUG.fullmatch(slug) or slug in seen:
            raise ValueError(f"Invalid or duplicate candidate {slug}")
        if not candidate["upstream"].startswith("https://"):
            raise ValueError(f"Candidate requires HTTPS upstream documentation: {slug}")
        if not isinstance(candidate.get("image"), str) or not candidate["image"]:
            raise ValueError(f"Missing image: {slug}")
        seen.add(slug)
        if slug not in existing:
            pending.append(candidate)
    return pending


def main() -> None:
    missing = missing_candidates()
    proc = subprocess.run(["gh", "issue", "list", "--state", "all", "--limit", "300",
                           "--json", "title"], capture_output=True, text=True, check=True)
    existing = {issue["title"] for issue in json.loads(proc.stdout)}
    for entry in missing:
        title = f"Nova aplicação candidata: {entry['slug']}"
        if title in existing:
            continue
        body = (f"Proposta automatizada (não aprovada): **{entry['slug']}**\n\n"
                f"Imagem upstream sugerida: `{entry['image']}`\n"
                f"Documentação: {entry['upstream']}\n"
                f"Notas: {entry.get('notes', '')}\n\n"
                "Antes de adicionar: confirmar origem/licença, Docker Compose ZimaOS v2, "
                "arquiteturas, volumes persistentes, credenciais, Trivy completo, "
                "testes de instalação e atualização. Criar PR individual; nunca instalar automaticamente.")
        subprocess.run(["gh", "issue", "create", "--title", title, "--body", body], check=True)
        print("Created candidate issue:", entry["slug"])
    print(f"Candidate check complete: {len(missing)} apps not yet in the store")


if __name__ == "__main__":
    main()
