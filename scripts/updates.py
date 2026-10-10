"""Observe Docker registry digests without changing source apps or installed containers.

Floating tags are monitored by SHA256 digest; the Renovate bot can separately
propose new semver tags, but it must be enabled on the GitHub repository.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import time
from catalog import ROOT, apps, image_usage

SHA256 = re.compile(r'^sha256:[a-f0-9]{64}$')


def digest(image: str, binary: str = 'crane') -> tuple[str | None, str | None]:
    """Retry short-lived registry outages; preserve persistent errors in the report."""
    transient_signals = (
        'timed out', 'timeout', '429', 'too many requests',
        '502', '503', '504', 'connection reset', 'connection refused',
        'temporary failure', 'temporarily unavailable', 'tls handshake',
    )
    for attempt in range(3):
        timed_out = False
        try:
            p = subprocess.run([binary, 'digest', image], capture_output=True,
                               text=True, timeout=90, check=False)
        except subprocess.TimeoutExpired as exc:
            error = str(exc)
            timed_out = True
        except OSError as exc:
            error = str(exc)
        else:
            actual = p.stdout.strip()
            if p.returncode == 0 and SHA256.fullmatch(actual):
                return actual, None
            error = (p.stderr or actual or f'crane exited {p.returncode}').strip()[:240]
        transient = timed_out or any(signal in error.lower() for signal in transient_signals)
        if attempt < 2 and transient:
            time.sleep(3 * (attempt + 1))
            continue
        return None, error
    raise AssertionError('Unreachable retry state')


def monitor(usage: dict[str, list[str]], before: dict, resolver=digest, workers: int = 4) -> tuple[dict, dict]:
    prior = before.get('images', {})
    state = {name: prior[name] for name in usage if name in prior}
    changed, unseen, failures = [], [], []
    with ThreadPoolExecutor(max_workers=max(1, min(8, workers))) as executor:
        jobs = {executor.submit(resolver, ref): ref for ref in usage}
        for future in as_completed(jobs):
            image = jobs[future]
            try:
                value, error = future.result()
            except Exception as exc:
                value, error = None, str(exc)
            if error or not value or not SHA256.fullmatch(value):
                failures.append({'image': image, 'error': error or 'invalid registry digest'})
                continue
            if image not in prior:
                unseen.append({'image': image, 'digest': value, 'apps': usage[image]})
            elif prior[image] != value:
                changed.append({'image': image, 'old': prior[image], 'new': value, 'apps': usage[image]})
            state[image] = value
    result = {'checked_at': datetime.now(timezone.utc).isoformat(), 'images': dict(sorted(state.items()))}
    details = {'checked': len(usage), 'resolved': len(usage)-len(failures),
               'changed': sorted(changed, key=lambda x: x['image']),
               'first_seen': sorted(unseen, key=lambda x: x['image']),
               'failed': sorted(failures, key=lambda x: x['image'])}
    return result, details


def summarize(details: dict) -> str:
    lines = ['# Alterações de imagens Docker — MrStore', '',
             f"Consultadas: {details['checked']} | resolvidas: {details['resolved']} | alterações: {len(details['changed'])} | novas: {len(details['first_seen'])} | falhas: {len(details['failed'])}", '',
             'Mudança de digest não garante nova versão nem instalação no ZimaOS. Nenhuma atualização é aplicada automaticamente.', '']
    for item in details['changed']:
        lines.append(f"- **{item['image']}** `{item['old'][:20]}` → `{item['new'][:20]}` ({', '.join(item['apps'])})")
    for item in details['failed']:
        lines.append(f"- ⚠️ `{item['image']}` — {item['error']}")
    return '\n'.join(lines)+'\n'


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--snapshot', type=Path, default=ROOT/'data/image-digests.json')
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--output', type=Path, default=ROOT/'out/updates.json')
    p.add_argument('--summary', type=Path, default=ROOT/'out/updates.md')
    opts = p.parse_args()
    previous = json.loads(opts.snapshot.read_text(encoding='utf-8')) if opts.snapshot.exists() else {'images': {}}
    snapshot, details = monitor(image_usage(apps(opts.root)), previous, workers=opts.workers)
    # Keep the last successful baseline on partial registry/network failures.
    # Preserve diagnostics even if a single image cannot be resolved; next run
    # must still compare against the last *complete* set of observations.
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    opts.output.write_text(json.dumps(details, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    opts.summary.parent.mkdir(parents=True, exist_ok=True)
    opts.summary.write_text(summarize(details), encoding='utf-8')
    if not details['failed'] and details['resolved'] == details['checked']:
        opts.snapshot.parent.mkdir(parents=True, exist_ok=True)
        opts.snapshot.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(f"Digests: {details['resolved']}/{details['checked']}; changed {len(details['changed'])}; failed {len(details['failed'])}")
    return 2 if details['failed'] else 0

if __name__ == '__main__':
    raise SystemExit(main())
