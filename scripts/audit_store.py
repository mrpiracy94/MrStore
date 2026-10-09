"""Fast, offline source validation + Docker Compose security posture review."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from storelib import ROOT, VALID_CATEGORIES, load_catalog, images_from_catalog


def audit(root=ROOT):
    apps = load_catalog(root)
    findings, ids, ports = [], set(), defaultdict(list)
    def finding(level, app, rule, detail):
        findings.append({'level': level, 'app': app, 'rule': rule, 'detail': str(detail)})
    for app, (doc, path) in apps.items():
        meta = doc.get('x-casaos') or {}
        services = doc.get('services') or {}
        if not isinstance(services, dict) or not services:
            finding('error', app, 'services', 'Missing services mapping'); continue
        if doc.get('name') != app:
            finding('warning', app, 'compose_name', f"{doc.get('name')!r} != directory")
        identifier = meta.get('id', '')
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)+', identifier):
            finding('error', app, 'id', 'Missing or invalid stable app id')
        elif identifier in ids:
            finding('error', app, 'duplicate_id', identifier)
        else: ids.add(identifier)
        for field in ('main','title','icon','version','port_map','index'):
            if not meta.get(field) and meta.get(field) != '0':
                finding('error', app, 'metadata', f'Missing {field}')
        if meta.get('main') not in services:
            finding('error', app, 'main', 'main is not an existing service')
        if meta.get('category') not in VALID_CATEGORIES:
            finding('error', app, 'category', meta.get('category'))
        if not isinstance(meta.get('title'), dict) or 'en_US' not in meta['title']:
            finding('error', app, 'title', 'Missing en_US title')
        if not isinstance(meta.get('port_map'), str):
            finding('error', app, 'port_map', 'Must be a quoted string')
        if meta.get('port_map') == '0':
            finding('warning', app, 'headless', 'No web UI port; do not expect browser launch')
        for name, cfg in services.items():
            if not isinstance(cfg,dict):
                finding('error',app,'service',name); continue
            img = cfg.get('image')
            if not img: finding('error', app,'image',f'{name}: no image')
            if isinstance(img,str) and not '@sha256:' in img and (':' not in img.split('/')[-1] or img.split(':')[-1] in ('latest','stable','release','main')):
                finding('warning',app,'mutable_tag',f'{name}: {img}')
            if cfg.get('privileged') is True: finding('warning',app,'privileged',name)
            if cfg.get('network_mode') == 'host': finding('warning',app,'host_network',name)
            if cfg.get('cap_add'):finding('warning',app,'cap_add',f"{name}: {cfg['cap_add']}")
            if 'seccomp:unconfined' in str(cfg.get('security_opt', [])):
                finding('warning',app,'seccomp_unconfined',name)
            for v in cfg.get('volumes', []):
                source = v.get('source','') if isinstance(v,dict) else v.split(':')[0]
                if source in ('/var/run/docker.sock','/','/etc','/root'):
                    finding('warning',app,'sensitive_mount',f'{name}: {source}')
            for v in cfg.get('environment',[]) if isinstance(cfg.get('environment',[]),list) else []:
                if 'CHANGE_ME' in str(v):finding('warning',app,'placeholder_secret',f'{name}: manual configuration required')
            for mapping in cfg.get('ports',[]):
                if isinstance(mapping,dict) and mapping.get('published'):
                    ports[str(mapping['published'])].append(app)
    for port, used in ports.items():
        if len(set(used))>1:
            finding('warning','*','host_port_collision',f'{port}: {", ".join(sorted(set(used)))}')
    report = {'apps': len(apps), 'images': len(images_from_catalog(apps)),
              'services':sum(len((d.get('services') or {})) for d,_ in apps.values()),
              'counts':dict(Counter(x['level'] for x in findings)),
              'rules':dict(Counter(x['rule'] for x in findings)), 'findings':findings}
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--out',type=Path);parser.add_argument('--strict',action='store_true')
    args=parser.parse_args(); report=audit(args.root)
    content=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.out: args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(content)
    print(f"Apps: {report['apps']} | images: {report['images']} | services: {report['services']} | findings: {report['counts']}")
    print('Rules:',report['rules'])
    if args.strict and report['counts'].get('error'): raise SystemExit(1)
if __name__=='__main__':main()
