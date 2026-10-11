#!/usr/bin/env python3
"""Fixar imagens da loja editorial em digests conhecidos, antes de publicar.

A baseline NAO prova ausencia de CVEs. Falha fechado perante referencias
desconhecidas ou alteradas. Nunca modifica os manifests originais Apps/.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

import yaml

SHA = re.compile(r"^sha256:[a-f0-9]{64}$")
IMAGE_LINE = re.compile(r"(?m)^([ \t]*image:[ \t]*)(\S+?)([ \t]*(?:#.*)?)$")


class PinError(ValueError):
    pass


def _digest(ref: str, images: dict) -> str:
    value = images.get(ref)
    if value is None and "@sha256:" in ref:
        value = images.get(ref.split("@sha256:", 1)[0])
    if not isinstance(value, str) or SHA.fullmatch(value) is None:
        raise PinError(f"Sem digest valido na baseline: {ref}")
    if "@sha256:" in ref and ref.rsplit("@", 1)[1] != value:
        raise PinError(f"Digest do manifesto difere da baseline: {ref}")
    return value


def pin_text(text: str, images: dict) -> tuple[str, int]:
    doc = yaml.safe_load(text)
    services = doc.get("services") if isinstance(doc, dict) else None
    if not isinstance(services, dict) or not services:
        raise PinError("Compose sem services validos")
    refs = [spec.get("image") for spec in services.values()
            if isinstance(spec, dict)]
    if len(refs) != len(services) or not all(isinstance(ref, str) for ref in refs):
        raise PinError("Servicos sem image em string nao suportados")
    for ref in refs:
        _digest(ref, images)
    found = Counter()

    def pin(match):
        lead, original, suffix = match.groups()
        quote = original[0] if original.startswith(('"', "'")) else ""
        if quote and original[-1] != quote:
            raise PinError("Quoting YAML de imagem nao suportado")
        ref = original[1:-1] if quote else original
        found[ref] += 1
        return f"{lead}{quote}{ref if '@sha256:' in ref else ref + '@' + _digest(ref, images)}{quote}{suffix}"

    updated = IMAGE_LINE.sub(pin, text)
    if found != Counter(refs):
        raise PinError("Numero de linhas image nao corresponde aos servicos")
    checked = yaml.safe_load(updated)
    for spec in checked["services"].values():
        if "@sha256:" not in spec["image"]:
            raise PinError("Uma imagem permaneceu sem digest")
    return updated, len(refs)


def pin_stage(root: Path, baseline: dict) -> tuple[int, int]:
    refs = baseline.get("images") if isinstance(baseline, dict) else None
    if not isinstance(refs, dict):
        raise PinError("Baseline sem mapa de images")
    paths = sorted((root / "Apps").glob("*/docker-compose.yml"))
    if not paths:
        raise PinError("Stage editorial sem Apps")
    updates = {}
    services = 0
    # Validar TODOS os manifests antes de modificar QUALQUER ficheiro.
    for path in paths:
        updated, count = pin_text(path.read_text(encoding="utf-8"), refs)
        updates[path] = updated
        services += count
    for path, updated in updates.items():
        path.write_text(updated, encoding="utf-8")
    return len(paths), services


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.stage.resolve()
        if root == Path.cwd().resolve() or root.name == "Apps":
            raise PinError("Recusa alterar diretorio raiz ou Apps originais")
        base = json.loads(args.baseline.read_text(encoding="utf-8"))
        apps, images = pin_stage(root, base)
    except (PinError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"PUBLICACAO BLOQUEADA: {exc}", file=sys.stderr)
        return 2
    print(f"{apps} apps e {images} imagens fixadas. CVE/certificacao: nao avaliados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
