"""Scan a deterministic shard of unique images using Trivy, preserving errors.

No image is deployed, CVEs do not prove exploitability, and a clean result
only means no reported HIGH/CRITICAL vulnerabilities in scanned images.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import time
from catalog import ROOT, apps, image_usage


def shard_images(images: dict | list, shard: int, shards: int) -> list[str]:
    if shards < 1 or not 0 <= shard < shards:
        raise ValueError('Invalid scan shard')
    return [image for i, image in enumerate(sorted(images)) if i % shards == shard]


# Limit transient registry requests instead of mistaking them for safe images.
# The remote-only source avoids false containerd socket errors in Actions.
RETRYABLE = re.compile(
    r'TOOMANYREQUESTS|429\\b|rate.?limit|retry.after|timeout|timed out|'
    r'connection reset|unexpected EOF|TLS handshake|context deadline|'
    r'temporar(?:y|ily) unavailable|connection refused|502 Bad Gateway|'
    r'503 Service Unavailable|504 Gateway Timeout',
    re.IGNORECASE,
)
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (12, 36)


def scan(image: str, binary: str = 'trivy', platform: str | None = None) -> tuple[list[dict], str | None]:
    args = [binary, 'image', '--quiet', '--scanners', 'vuln', '--severity', 'HIGH,CRITICAL',
            '--image-src', 'remote', '--parallel', '2',
            '--format', 'json', '--timeout', '8m']
    if platform is not None:
        if platform not in ('amd64', 'arm64'):
            raise ValueError('Unsupported scan platform')
        args.extend(['--platform', 'linux/' + platform])
    args.append(image)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            p = subprocess.run(args, capture_output=True, text=True, check=False, timeout=550)
            if p.returncode:
                error = (p.stderr or p.stdout or f'Trivy exited {p.returncode}').strip()[-900:]
            else:
                try:
                    report = json.loads(p.stdout)
                except ValueError:
                    return [], 'Invalid Trivy JSON output'
                if not isinstance(report, dict) or not isinstance(report.get('Results'), list):
                    return [], 'Incomplete Trivy report (missing Results)'
                # A successful Trivy exit with zero analysed targets cannot
                # certify an image as free from HIGH/CRITICAL vulnerabilities.
                if not report['Results']:
                    return [], 'Incomplete Trivy report (no scan targets)'
                if any(not isinstance(result, dict) or
                       not isinstance(result.get('Target'), str) or
                       not result['Target'].strip()
                       for result in report['Results']):
                    return [], 'Incomplete Trivy report (invalid scan target)'
                hits = []
                seen = set()
                for result in report['Results']:
                    if not isinstance(result, dict):
                        continue
                    for item in result.get('Vulnerabilities') or []:
                        if item.get('Severity') not in ('HIGH', 'CRITICAL'):
                            continue
                        key = (item.get('VulnerabilityID'), item.get('PkgName'),
                               item.get('InstalledVersion'), result.get('Target'))
                        if key in seen:
                            continue
                        seen.add(key)
                        hits.append({'cve': item.get('VulnerabilityID'),
                                     'severity': item.get('Severity'),
                                     'package': item.get('PkgName'),
                                     'installed': item.get('InstalledVersion'),
                                     'fixed': item.get('FixedVersion'),
                                     'target': result.get('Target'),
                                     'url': item.get('PrimaryURL')})
                return hits, None
        except subprocess.TimeoutExpired as exc:
            error = str(exc)
        except OSError as exc:
            return [], str(exc)

        if attempt == MAX_ATTEMPTS or not RETRYABLE.search(error):
            return [], f'Trivy failed ({attempt}/{MAX_ATTEMPTS} attempts): {error}'
        seconds = BACKOFF_SECONDS[attempt - 1]
        print(f'Trivy transient error on {image} ({attempt}/{MAX_ATTEMPTS}); '
              f'retrying after {seconds}s', flush=True)
        time.sleep(seconds)

    raise AssertionError('Unreachable retry state')


def select_images(usage: dict[str, list[str]], images_file: Path | None) -> list[str]:
    if images_file is None:
        return sorted(usage)
    requested = json.loads(images_file.read_text(encoding='utf-8'))
    if not isinstance(requested, list) or not requested or any(
        not isinstance(image, str) for image in requested
    ):
        raise ValueError('Image subset must be a non-empty JSON list of strings')
    if len(set(requested)) != len(requested):
        raise ValueError('Image subset contains duplicate references')
    unknown = sorted(set(requested) - usage.keys())
    if unknown:
        raise ValueError(f'Subset includes images no longer in catalog: {unknown}')
    return sorted(requested)


def evaluate(usage: dict[str,list[str]], chosen: list[str], scanner=scan) -> dict:
    results = []
    for index, image in enumerate(chosen, 1):
        print(f'[{index}/{len(chosen)}] {image}', flush=True)
        try:
            vulns, error = scanner(image)
        except Exception as exc:
            vulns, error = [], str(exc)
        results.append({'image': image, 'apps': usage[image], 'status': 'error' if error else 'ok',
                        'error': error, 'findings': vulns})
    return {'scanned_at': datetime.now(timezone.utc).isoformat(), 'images_total': len(usage),
            'images_checked': len(chosen), 'failures': sum(x['status']=='error' for x in results),
            'critical': sum(y['severity']=='CRITICAL' for x in results for y in x['findings']),
            'high': sum(y['severity']=='HIGH' for x in results for y in x['findings']),
            'results': results}


def summarize(report: dict, shard: int, shards: int) -> str:
    lines = ['# Auditoria CVE — MrStore', '',
             f"Shard {shard+1}/{shards} | {report['images_checked']}/{report['images_total']} imagens | {report['critical']} CRITICAL | {report['high']} HIGH | falhas: {report['failures']}", '',
             'A presença de CVE não comprova exploração possível; ausência de alertas não garante segurança. Falhas de scanner não são contadas como imagens limpas.', '']
    for entry in report['results']:
        if entry['status'] == 'error':
            lines.append(f"- ⚠️ `{entry['image']}`: {entry['error']}")
        elif entry['findings']:
            hi=sum(f['severity']=='HIGH' for f in entry['findings'])
            cr=sum(f['severity']=='CRITICAL' for f in entry['findings'])
            fixes=sum(bool(f.get('fixed')) for f in entry['findings'])
            lines.append(f"- `{entry['image']}`: {cr} CRITICAL, {hi} HIGH; {fixes} com versão corrigida ({', '.join(entry['apps'])})")
            # Show actionable critical packages in GitHub issues, not just counts.
            critical = sorted((v for v in entry['findings'] if v['severity'] == 'CRITICAL'),
                              key=lambda v: (not bool(v.get('fixed')), v.get('cve') or ''))
            for finding in critical[:4]:
                available = (f" → `{finding['fixed']}`" if finding.get('fixed')
                             else " (sem versão corrigida anunciada)")
                lines.append(f"  - `{finding['cve']}` / `{finding['package']}`: "
                             f"`{finding.get('installed') or 'desconhecida'}`{available}")
            if len(critical) > 4:
                lines.append(f"  - Mais {len(critical)-4} ocorrências CRITICAL no artifact JSON.")
    lines.extend(['', 'Versões corrigidas referem-se a pacotes, não garantem '
                  'que uma imagem Docker compatível já esteja disponível. '
                  'Atualiza/testa a imagem e repete o scan; nunca migres uma base de dados '
                  'sem backup e plano de compatibilidade.'])
    return '\n'.join(lines)+'\n'


def audit_exit_status(report: dict) -> int:
    """Never mark a scan clean when HIGH/CRITICAL findings or lookup failures remain."""
    if report['failures']:
        return 2
    if report['critical'] or report['high']:
        return 3
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--images-file', type=Path, help='Optional explicit image subset for diagnosis')
    p.add_argument('--shards', type=int, default=8)
    p.add_argument('--shard', type=int, default=0)
    p.add_argument('--output', type=Path, default=ROOT/'out/cves.json')
    p.add_argument('--summary', type=Path, default=ROOT/'out/cves.md')
    opts = p.parse_args()
    usage = image_usage(apps(opts.root))
    chosen = shard_images(select_images(usage, opts.images_file), opts.shard, opts.shards)
    report = evaluate(usage, chosen)
    report['shard'] = opts.shard
    report['shards'] = opts.shards
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    opts.output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    opts.summary.write_text(summarize(report, opts.shard, opts.shards), encoding='utf-8')
    print(f"CVE: {report['critical']} CRITICAL; {report['high']} HIGH; errors {report['failures']}")
    return audit_exit_status(report)

if __name__ == '__main__':
    raise SystemExit(main())
