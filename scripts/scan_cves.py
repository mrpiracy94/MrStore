"""Trivy CVE scan for one of N deterministic rotating catalog shards."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from storelib import ROOT, load_catalog, images_from_catalog


def image_slice(images, shard, shards):
    if shards < 1 or not (0 <= shard < shards): raise ValueError('Invalid shard')
    return [name for pos,name in enumerate(sorted(images)) if pos % shards == shard]


def scan(image, trivy='trivy'):
    cmd=[trivy,'image','--quiet','--scanners','vuln','--severity','HIGH,CRITICAL',
         '--format','json','--timeout','5m',image]
    try: result=subprocess.run(cmd,capture_output=True,text=True,timeout=420,check=False)
    except (OSError,subprocess.TimeoutExpired) as e:return [],str(e)
    if result.returncode:return [],(result.stderr or f'exit {result.returncode}')[-400:]
    try:data=json.loads(result.stdout)
    except (ValueError,TypeError):return [],'Could not parse Trivy JSON'
    vulnerabilities=[]
    for target in data.get('Results',[]) or []:
        for v in target.get('Vulnerabilities') or []:
            vulnerabilities.append({'id':v.get('VulnerabilityID'), 'severity':v.get('Severity'),
                'package':v.get('PkgName'), 'installed':v.get('InstalledVersion'),
                'fixed':v.get('FixedVersion'),'target':target.get('Target')})
    return vulnerabilities,None


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--shard',type=int,default=0);p.add_argument('--shards',type=int,default=8)
    p.add_argument('--out',type=Path,default=ROOT/'out/cve-results.json')
    p.add_argument('--summary-out',type=Path,default=ROOT/'out/cve-summary.md')
    a=p.parse_args()
    usage=images_from_catalog(load_catalog(a.root)); chosen=image_slice(usage,a.shard,a.shards)
    outcomes=[]
    for i,image in enumerate(chosen,1):
        print(f'[{i}/{len(chosen)}] Scanning {image}',flush=True)
        vulns,error=scan(image)
        outcomes.append({'image':image,'apps':usage[image], 'status':'error' if error else 'ok',
                         'error':error,'vulnerabilities':vulns})
    report={'scanned_at':datetime.now(timezone.utc).isoformat(),'shard':a.shard,'shards':a.shards,
            'images_in_catalog':len(usage),'results':outcomes}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n')
    errors=[r for r in outcomes if r['status']=='error']
    count=sum(len(r['vulnerabilities']) for r in outcomes)
    lines=['# CVE scan — Trivy','',f"Shard: {a.shard+1}/{a.shards} | scanned: {len(outcomes)} images of {len(usage)} | findings: {count} | errors: {len(errors)}",'']
    lines+=['Image vulnerability findings are package-level, can have duplicates, and do not prove exploitability.','']
    for r in outcomes:
        if r['status']=='error':lines.append(f"- ⚠️ {r['image']}: {r['error']}")
        elif r['vulnerabilities']:
            high=sum(v.get('severity')=='HIGH' for v in r['vulnerabilities']);critical=sum(v.get('severity')=='CRITICAL' for v in r['vulnerabilities'])
            lines.append(f"- {r['image']}: {critical} critical, {high} high | {', '.join(r['apps'])}")
    a.summary_out.parent.mkdir(parents=True,exist_ok=True)
    a.summary_out.write_text('\n'.join(lines)+'\n')
    print(f'Image scan results: {len(outcomes)} images, {count} findings, {len(errors)} errors')
    if errors:raise SystemExit(2)
if __name__=='__main__':main()
