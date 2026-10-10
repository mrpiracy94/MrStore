"""Add PT-PT descriptions to approved release metadata without altering Docker settings.

Fallbacks are explicitly derived from the manually curated, app-specific PT
subtitles; existing full Portuguese descriptions always take precedence.
"""
from __future__ import annotations


def enrich(metadata: dict, curated_pt_summary: str) -> bool:
    descriptions = metadata.get("description")
    if not isinstance(descriptions, dict) or not descriptions.get("en_US"):
        raise ValueError("Every published app needs an English description")
    if descriptions.get("pt_PT", "").strip():
        return False
    summary = curated_pt_summary.strip().rstrip(" .")
    if not summary:
        raise ValueError("Empty curated PT summary")
    descriptions["pt_PT"] = (
        summary + ". Antes de instalar, consulta a documentação do projeto e "
        "confirma os requisitos, as permissões, as portas e os volumes necessários. "
        "Define credenciais fortes quando aplicável e mantém cópias de segurança."
    )
    return True
