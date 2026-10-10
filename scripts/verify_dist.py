"""Check protocol-v2 publication completeness, not just builder exit status."""
import argparse
import json
from pathlib import Path
import re
import sys


def verify(root: Path, expected: int) -> int:
    root = root.resolve()
    for name in ('store.json', 'index.json'):
        if not (root / name).is_file():
            raise ValueError(f'Missing generated {name}')
    store=json.loads((root/'store.json').read_text(encoding='utf-8'))
    index=json.loads((root/'index.json').read_text(encoding='utf-8'))
    if store.get('version') != 2 or index.get('version') != 2:
        raise ValueError('Unsupported ZimaOS store/index protocol version')
    items=index.get('apps')
    if not isinstance(items, list):
        raise ValueError('index.json apps must be a list')
    if len(items) != expected or index.get('app_count') != expected:
        raise ValueError(f'Expected {expected} apps, found {len(items)} in index (reported {index.get("app_count")})')
    found=set()
    for entry in items:
        if not isinstance(entry, dict):
            raise ValueError('Invalid index entry')
        app_id=entry.get('id','')
        if (not isinstance(app_id, str) or app_id in found or '..' in app_id
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', app_id)):
            raise ValueError(f'Invalid/duplicate ID in index: {app_id!r}')
        found.add(app_id)
        for field in ('compose_url','meta_url','icon','content_hash','version'):
            if not entry.get(field):
                raise ValueError(f'{app_id} missing {field}')
        app_folder=root/'apps'/app_id
        if not app_folder.resolve().is_relative_to(root):
            raise ValueError(f'{app_id}: app directory escapes release root')
        if not (app_folder/'docker-compose.yml').is_file() or not (app_folder/'meta.json').is_file():
            raise ValueError(f'{app_id} has missing generated compose or metadata')
        # Manifest/metadata URLs must identify this exact app, not a different
        # existing app or an attacker-controlled external endpoint.
        for field, filename in (('compose_url', 'docker-compose.yml'), ('meta_url', 'meta.json')):
            required_url = f'/apps/{app_id}/{filename}'
            if entry[field] != required_url:
                raise ValueError(f'{app_id}: invalid generated {field}: {entry[field]!r}')
        for field in ('icon','thumbnail'):
            url=entry.get(field)
            if isinstance(url,str) and url.startswith('/apps/'):
                relative=url.lstrip('/')
                target=(root/relative).resolve()
                if ('..' in Path(relative).parts or not target.is_relative_to(root)
                        or not target.is_file()):
                    raise ValueError(f'{app_id}: broken generated {field}: {url}')
    meta=list((root/'apps').glob('*/meta.json'))
    compose=list((root/'apps').glob('*/docker-compose.yml'))
    if len(meta)!=expected or len(compose)<expected:
        raise ValueError(f'File count mismatch: {len(meta)} meta, {len(compose)} compose; expected {expected}')
    print(f'ZimaOS v2 verified: {expected} apps, unique IDs, icons, metadata, compose URLs and content hashes')
    return len(items)


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--dist',type=Path,default=Path('dist'))
    p.add_argument('--expected',type=int,default=254)
    opts=p.parse_args()
    try: verify(opts.dist,opts.expected)
    except (ValueError,OSError) as exc:
        print('Publish verification failed:',exc,file=sys.stderr)
        raise SystemExit(1)
