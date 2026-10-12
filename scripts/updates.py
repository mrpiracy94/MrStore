"""Observe Docker registry digests without changing source apps or installed containers.

Compare mutable tags against the SHA256 pinned in every source Compose; the Renovate bot can separately
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
    """Compare LIVE mutable registry tags with the REVIEWED immutable Compose baseline.

    Resolve the tag, NEVER the manifest's @sha256 reference: resolving an already
    pinned image simply returns its old digest and hides available updates.
    The returned snapshot is diagnostics only and is not an approval baseline.
    """
    prior = before.get('images', {})
    if not isinstance(prior, dict):
        raise ValueError('Malformed reviewed digest baseline')
    state = dict(prior)
    changed, unseen, failures = [], [], []
    eligible = {}
    pinned = re.compile(r'^(.+)@(sha256:[0-9a-f]{64})$')
    for image, app_refs in usage.items():
        match = pinned.fullmatch(image)
        tag = match.group(1) if match else image
        approved = prior.get(image, prior.get(tag))
        if match and (not SHA256.fullmatch(str(approved)) or match.group(2) != approved):
            failures.append({'image': image, 'error': 'Pinned digest is missing from or differs from reviewed baseline'})
            continue
        if not match and approved is not None and not SHA256.fullmatch(str(approved)):
            failures.append({'image': image, 'error': 'Reviewed baseline contains invalid digest'})
            continue
        if tag in eligible:
            if eligible[tag]['approved'] != approved:
                failures.append({'image': image, 'error': 'Conflicting approved digests for the same tag'})
            else:
                eligible[tag]['apps'].update(app_refs)
            continue
        eligible[tag] = {'original': image, 'approved': approved, 'apps': set(app_refs)}
    with ThreadPoolExecutor(max_workers=max(1, min(8, workers))) as executor:
        jobs = {executor.submit(resolver, tag): tag for tag in eligible}
        for future in as_completed(jobs):
            tag = jobs[future]
            entry = eligible[tag]
            try:
                value, error = future.result()
            except Exception as exc:
                value, error = None, str(exc)
            if error or not value or not SHA256.fullmatch(value):
                failures.append({'image': tag, 'error': error or 'Invalid registry digest'})
                continue
            old = entry['approved']
            app_refs = sorted(entry['apps'])
            if old is None:
                unseen.append({'image': tag, 'digest': value, 'apps': app_refs})
            elif old != value:
                changed.append({'image': tag, 'source_image': entry['original'],
                                'old': old, 'new': value, 'apps': app_refs})
            # Only the diagnostic snapshot receives the live digest.
            # Committed data/image-digests.json must NEVER change in this script.
            state[tag] = value
    result = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'images': dict(sorted(state.items()))}
    details = {'checked': len(usage), 'resolved': len(eligible) - (len(failures) - (len(usage) - len(eligible))),
               'changed': sorted(changed, key=lambda x: x['image']),
               'first_seen': sorted(unseen, key=lambda x: x['image']),
               'failed': sorted(failures, key=lambda x: x['image'])}
    # Count complete image references, not only successful unique tag lookups.
    details['resolved'] = len(usage) - len(failures)
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
        # Nunca sobrescrever a baseline aprovada; guardar evidência separada.
        live = opts.output.with_name('updates-live-digests.json')
        live.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(f"Digests: {details['resolved']}/{details['checked']}; changed {len(details['changed'])}; failed {len(details['failed'])}")
    return 2 if details['failed'] else 0

if __name__ == '__main__':
    raise SystemExit(main())
