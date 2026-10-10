"""Scan a deterministic shard of unique images using Trivy, preserving errors.

No image is deployed, CVEs do not prove exploitability, and a clean result
only means no reported HIGH/CRITICAL vulnerabilities in scanned images.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
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
    r'TOOMANYREQUESTS|429\b|rate.?limit|retry.after|timeout|timed out|'
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
    # Parallel daily scans share freshly prepared read-only databases.
    # Memory scan cache avoids Trivy's filesystem cache lock; release scans
    # retain their existing cache/update behaviour.
    if os.environ.get('MRSTORE_CVE_DB_PREPARED') == '1':
        args.extend(['--cache-backend', 'memory', '--skip-db-update',
                     '--skip-java-db-update'])
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
                # Validate all vulnerability records before interpreting any
                # report as clean. Malformed records are not zero CVEs.
                for result in report['Results']:
                    vulnerabilities = result.get('Vulnerabilities')
                    if vulnerabilities is not None and (
                            not isinstance(vulnerabilities, list) or
                            any(not isinstance(item, dict) for item in vulnerabilities)):
                        return [], 'Incomplete Trivy report (invalid vulnerabilities)'
                hits = []
                seen = set()
                for result in report['Results']:
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


def select_app_images(usage: dict[str, list[str]], folders: set[str],
                      strict: bool = True) -> list[str]:
    """Resolve all service images for an app; deduplicate shared references."""
    existing = {ref.split('/', 1)[0] for refs in usage.values() for ref in refs}
    unknown = folders - existing
    if strict and unknown:
        raise ValueError(f'Unknown application folders: {sorted(unknown)}')
    folders = folders & existing
    return sorted(image for image, refs in usage.items()
                  if any(ref.split('/', 1)[0] in folders for ref in refs))


def changed_apps_since(root: Path, base_sha: str) -> set[str]:
    """Only select committed app folders modified since a push's previous HEAD.

    Fail if Git cannot establish the comparison instead of silently
    presenting an unverified application as clean.
    """
    if not re.fullmatch(r'[0-9a-fA-F]{40}', base_sha):
        raise ValueError('Invalid base commit SHA for incremental CVE scan')
    result = subprocess.run(
        ['git', '-C', str(root), 'diff', '--name-only', '-z',
         base_sha, 'HEAD', '--', 'Apps/'],
        capture_output=True, text=True, check=True,
    )
    return {parts[1] for name in result.stdout.split('\\0') if name
            for parts in [Path(name).parts]
            if len(parts) >= 3 and parts[0] == 'Apps'}


def application_results(usage: dict[str, list[str]], results: list[dict]) -> dict:
    """Per-app evidence, never calling partially scanned apps clean."""
    all_images = {}
    for image, references in usage.items():
        for ref in references:
            all_images.setdefault(ref.split('/', 1)[0], set()).add(image)
    checked = {entry['image']: entry for entry in results}
    by_app = {}
    for folder, expected in sorted(all_images.items()):
        seen = expected & checked.keys()
        if not seen:
            continue
        entries = [checked[image] for image in sorted(seen)]
        high = sum(v.get('severity') == 'HIGH' for e in entries for v in e['findings'])
        critical = sum(v.get('severity') == 'CRITICAL' for e in entries for v in e['findings'])
        failures = sum(e['status'] == 'error' for e in entries)
        complete = len(seen) == len(expected)
        if critical or high:
            status = 'vulnerable'
        elif failures:
            status = 'inconclusive'
        elif not complete:
            status = 'partial'
        else:
            status = 'no_high_critical_detected'
        by_app[folder] = {'status': status, 'complete': complete,
                          'images_checked': len(seen), 'images_total': len(expected),
                          'high': high, 'critical': critical, 'failures': failures}
    return by_app


def evaluate(usage: dict[str, list[str]], chosen: list[str], scanner=scan,
             workers: int = 1) -> dict:
    if not 1 <= workers <= 4:
        raise ValueError('workers must be between 1 and 4')
    results = [None] * len(chosen)

    def inspect(image: str) -> dict:
        try:
            vulns, error = scanner(image)
        except Exception as exc:
            vulns, error = [], str(exc)
        return {'image': image, 'apps': usage[image],
                'status': 'error' if error else 'ok',
                'error': error, 'findings': vulns}

    if workers == 1:
        for index, image in enumerate(chosen):
            print(f'[{index + 1}/{len(chosen)}] {image}', flush=True)
            results[index] = inspect(image)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = {pool.submit(inspect, image): index
                       for index, image in enumerate(chosen)}
            for done_count, future in enumerate(as_completed(pending), 1):
                index = pending[future]
                results[index] = future.result()
                print(f'[{done_count}/{len(chosen)}] {chosen[index]}: '
                      f"{results[index]['status']}", flush=True)

    report = {
        'scanned_at': datetime.now(timezone.utc).isoformat(),
        'images_total': len(usage),
        'images_checked': len(chosen),
        'failures': sum(x['status'] == 'error' for x in results),
        'critical': sum(y['severity'] == 'CRITICAL' for x in results for y in x['findings']),
        'high': sum(y['severity'] == 'HIGH' for x in results for y in x['findings']),
        'results': results,
    }
    report['applications'] = application_results(usage, results)
    return report

def summarize(report: dict, shard: int, shards: int) -> str:
    lines = ['# Auditoria CVE — MrStore', '',
             f"Shard {shard+1}/{shards} | {report['images_checked']}/{report['images_total']} imagens | {report['critical']} CRITICAL | {report['high']} HIGH | falhas: {report['failures']}", '',
             'A presença de CVE não comprova exploração possível; ausência de alertas não garante segurança. Falhas de scanner não são contadas como imagens limpas.', '']
    if not report['results']:
        lines.append('Nenhuma imagem selecionada nesta execução; isto não é uma auditoria completa.')
    lines.extend(['', '## Resultado por aplicação (apenas imagens deste grupo)', ''])
    for folder, app in report.get('applications', {}).items():
        lines.append(f"- `{folder}`: **{app['status']}** — imagens "
                     f"{app['images_checked']}/{app['images_total']}, "
                     f"{app['critical']} CRITICAL, {app['high']} HIGH, "
                     f"{app['failures']} inconclusivas")
    lines.extend(['', '## Detalhes por imagem', ''])
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
    scope = p.add_mutually_exclusive_group()
    scope.add_argument('--images-file', type=Path, help='Explicit image subset for diagnosis')
    scope.add_argument('--app', help='Scan every service image belonging to one app folder')
    scope.add_argument('--changed-since', help='Scan app folders changed since this Git commit')
    p.add_argument('--workers', type=int, default=2, help='Concurrent image scans per job (1-4)')
    p.add_argument('--shards', type=int, default=8)
    p.add_argument('--shard', type=int, default=0)
    p.add_argument('--output', type=Path, default=ROOT/'out/cves.json')
    p.add_argument('--summary', type=Path, default=ROOT/'out/cves.md')
    opts = p.parse_args()
    usage = image_usage(apps(opts.root))
    selected = select_images(usage, opts.images_file)
    if opts.app:
        selected = select_app_images(usage, {opts.app})
    elif opts.changed_since:
        selected = select_app_images(usage, changed_apps_since(opts.root, opts.changed_since),
                                     strict=False)
    chosen = shard_images(selected, opts.shard, opts.shards)
    report = evaluate(usage, chosen, workers=opts.workers)
    report['scope'] = ('app' if opts.app else 'changed' if opts.changed_since else 'catalog')
    report['shard'] = opts.shard
    report['shards'] = opts.shards
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    opts.output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    opts.summary.write_text(summarize(report, opts.shard, opts.shards), encoding='utf-8')
    print(f"CVE: {report['critical']} CRITICAL; {report['high']} HIGH; errors {report['failures']}")
    return audit_exit_status(report)

if __name__ == '__main__':
    raise SystemExit(main())
