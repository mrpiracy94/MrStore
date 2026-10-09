"""Monitor manifest digests (not semantic upstream versions) via the crane CLI.

Initial run establishes baseline. Failed registry queries never overwrite previously
known digests. Changes are reported, not automatically deployed.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from storelib import ROOT, load_catalog, images_from_catalog

DIGEST = re.compile(r'^sha256:[0-9a-f]{64}$')


def resolve(image, command='crane'):
    try:
        process = subprocess.run([command, 'digest', image], capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    value = process.stdout.strip()
    if process.returncode != 0 or not DIGEST.fullmatch(value):
        return None, (process.stderr or value or f'exit {process.returncode}').strip()[:300]
    return value, None


def check(usage, previous, resolver=resolve, workers=4):
    prior = previous.get('images',{})
    state = dict(prior); changes=[]; new=[]; failures=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs={pool.submit(resolver, image):image for image in usage}
        for future in as_completed(jobs):
            image=jobs[future]
            try: digest, error=future.result()
            except Exception as exc: digest,error=None,str(exc)
            if error:
                failures.append({'image':image,'error':error})
                continue
            old=prior.get(image)
            state[image]=digest
            if old and old != digest:
                changes.append({'image':image,'previous':old,'current':digest,'used_by':usage[image]})
            elif not old:
                new.append({'image':image,'current':digest,'used_by':usage[image]})
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'images':dict(sorted(state.items()))}
    details={'changed':sorted(changes,key=lambda v:v['image']), 'new':sorted(new,key=lambda v:v['image']),
             'failed':sorted(failures,key=lambda v:v['image']), 'monitored':len(usage),
             'resolved':len(usage)-len(failures)}
    return result, details


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--snapshot',type=Path,default=ROOT/'data/image-digests.json')
    p.add_argument('--changes-out',type=Path,default=ROOT/'out/image-changes.json')
    p.add_argument('--summary-out',type=Path,default=ROOT/'out/image-changes.md')
    p.add_argument('--workers',type=int,default=4)
    a=p.parse_args()
    previous=json.loads(a.snapshot.read_text()) if a.snapshot.exists() else {'images':{}}
    state, details=check(images_from_catalog(load_catalog(a.root)),previous,workers=max(1,min(8,a.workers)))
    a.snapshot.parent.mkdir(parents=True,exist_ok=True)
    a.snapshot.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    a.changes_out.parent.mkdir(parents=True,exist_ok=True)
    a.changes_out.write_text(json.dumps(details,ensure_ascii=False,indent=2)+'\n')
    lines=['# Docker registry update monitor','',f"Resolved: {details['resolved']}/{details['monitored']}",
           f"Changed: {len(details['changed'])}; new/baseline: {len(details['new'])}; errors: {len(details['failed'])}",'',
           'Digest change = image has changed; NOT proof of a new upstream release or an installed app update.','']
    for item in details['changed']:
        lines.append(f"- **{item['image']}** (`{item['previous'][:20]}` → `{item['current'][:20]}`), apps: {', '.join(item['used_by'])}")
    for item in details['failed']:
        lines.append(f"- ⚠️ {item['image']}: {item['error']}")
    a.summary_out.write_text('\n'.join(lines)+'\n')
    print(f"Resolved {details['resolved']}/{details['monitored']} images, changed {len(details['changed'])}, first seen {len(details['new'])}, failed {len(details['failed'])}")
    # Do not treat a partial registry outage as a clean scan
    if details['failed']:raise SystemExit(2)
if __name__=='__main__':main()
