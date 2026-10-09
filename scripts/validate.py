"""Deterministic offline audit; warnings are visible, errors fail CI."""
import argparse
import json
from pathlib import Path
from catalog import ROOT, report


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--output', type=Path, default=ROOT/'out/audit.json')
    p.add_argument('--summary', type=Path, default=ROOT/'out/audit.md')
    args = p.parse_args()
    results = report(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    summary=results['summary']
    lines = ['# MrStore — validação do catálogo', '',
             f"Apps: {summary['apps']} · Serviços: {summary['services']} · Imagens: {summary['images']}",
             f"Erros: {summary['errors']} · Avisos: {summary['warnings']}", '',
             '## Tipos de ocorrências', '']
    for name, count in results['rules'].items():
        lines.append(f'- {name}: {count}')
    lines += ['', 'O scan offline não confirma CVEs nem disponibilidade das imagens Docker.', '']
    args.summary.parent.mkdir(parents=True,exist_ok=True)
    args.summary.write_text('\n'.join(lines), encoding='utf-8')
    print(' | '.join(f'{k}: {v}' for k,v in summary.items()))
    return 1 if summary['errors'] else 0

if __name__ == '__main__':
    raise SystemExit(main())
