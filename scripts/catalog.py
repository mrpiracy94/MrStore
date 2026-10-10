"""Read ZimaOS Compose manifests as inert YAML; never run untrusted app definitions."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import json
import re
from urllib.parse import urlparse
import yaml

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = frozenset('Media Productivity Home Networking AI Finance Social Developer Others'.split())
APP_ID = re.compile(r'^[a-z0-9][a-z0-9._-]*$')
LOCAL_ASSET = 'https://raw.githubusercontent.com/mrpiracy94/MrStore/main/'

@dataclass(frozen=True)
class App:
    folder: str
    path: Path
    source: dict
    metadata: dict
    @property
    def app_id(self) -> str:
        return str(self.metadata.get('id', ''))


def apps(root: Path = ROOT) -> list[App]:
    sources = sorted((Path(root) / 'Apps').glob('*/docker-compose.yml'))
    if not sources:
        raise ValueError('No applications found in Apps/*/docker-compose.yml')
    out: list[App] = []
    for path in sources:
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError(f'{path}: compose is not an object')
        meta = data.get('x-casaos')
        out.append(App(path.parent.name, path, data, meta if isinstance(meta, dict) else {}))
    return out


def image_usage(items: list[App]) -> dict[str, list[str]]:
    references = defaultdict(list)
    for app in items:
        services = app.source.get('services') or {}
        if not isinstance(services, dict):
            continue
        for service, spec in services.items():
            if isinstance(spec, dict) and isinstance(spec.get('image'), str):
                references[spec['image']].append(f'{app.folder}/{service}')
    return dict(sorted((k, sorted(v)) for k, v in references.items()))


def local_asset_missing(url: object, root: Path) -> str | None:
    if not isinstance(url, str) or not url.startswith(LOCAL_ASSET):
        return None
    relative = url[len(LOCAL_ASSET):]
    # Do not allow absolute paths or traversal from manifest assets.
    candidate = Path(relative)
    if candidate.is_absolute() or '..' in candidate.parts:
        return f'unsafe local asset path: {relative}'
    if not (root / candidate).is_file():
        return f'missing local asset: {relative}'
    return None


def report(root: Path = ROOT) -> dict:
    root = Path(root)
    items = apps(root)
    # Import after catalog initialization: privilege_policy imports catalog.
    from privilege_policy import sensitive_host_bind
    issues: list[dict] = []
    seen_ids: set[str] = set()
    used_ports = defaultdict(set)
    def add(level: str, name: str, code: str, message: str) -> None:
        issues.append({'level': level, 'app': name, 'code': code, 'message': message})
    for app in items:
        meta = app.metadata
        services = app.source.get('services')
        if not isinstance(services, dict) or not services:
            add('error', app.folder, 'services', 'missing services mapping')
            continue
        if not APP_ID.fullmatch(app.app_id):
            add('error', app.folder, 'id', 'invalid or missing x-casaos.id')
        elif app.app_id in seen_ids:
            add('error', app.folder, 'id_duplicate', app.app_id)
        else:
            seen_ids.add(app.app_id)
        if app.source.get('name') != app.folder:
            add('warning', app.folder, 'compose_name', 'compose project name differs from directory')
        for field in ('version', 'icon', 'thumbnail', 'port_map', 'index'):
            if meta.get(field) is None or meta.get(field) == '':
                add('error', app.folder, 'required', f'missing x-casaos.{field}')
        if not isinstance(meta.get('title'), dict) or not isinstance(meta['title'].get('en_US'), str):
            add('error', app.folder, 'title', 'missing en_US title')
        if meta.get('main') not in services:
            add('error', app.folder, 'main', 'x-casaos.main does not match a service')
        if meta.get('category') not in CATEGORIES:
            add('error', app.folder, 'category', str(meta.get('category')))
        if not isinstance(meta.get('port_map'), str):
            add('error', app.folder, 'port_map', 'must be a quoted string')
        if meta.get('port_map') == '0':
            add('warning', app.folder, 'headless_ui', 'no web UI: launch button may not work')
        if not meta.get('architectures') or not set(meta['architectures']) <= {'amd64', 'arm64'}:
            add('error', app.folder, 'architectures', 'must explicitly declare supported architectures')
        for field in ('icon', 'thumbnail'):
            missing = local_asset_missing(meta.get(field), root)
            if missing:
                add('error', app.folder, 'asset', missing)
        for service, spec in services.items():
            if not isinstance(spec, dict):
                add('error', app.folder, 'service', f'{service}: service is not an object')
                continue
            img = spec.get('image')
            if not isinstance(img, str) or not img.strip():
                add('error', app.folder, 'image', f'{service}: no image')
            elif img.rsplit(':', 1)[-1] in ('latest', 'stable', 'release', 'main') or ':' not in img.split('/')[-1]:
                add('warning', app.folder, 'mutable_image', f'{service}: {img}')
            if spec.get('privileged') is True:
                add('warning', app.folder, 'privileged', service)
            if spec.get('network_mode') == 'host':
                add('warning', app.folder, 'host_network', service)
            if spec.get('cap_add'):
                add('warning', app.folder, 'cap_add', service)
            if any('seccomp:unconfined' in str(x) for x in (spec.get('security_opt') or [])):
                add('warning', app.folder, 'seccomp_unconfined', service)
            for volume in spec.get('volumes') or []:
                if isinstance(volume, dict):
                    src = volume.get('source') if volume.get('type', 'bind') == 'bind' else None
                else:
                    src = str(volume).split(':', 1)[0]
                # Shared canonical detection includes parent paths and socket aliases.
                if sensitive_host_bind(src):
                    add('warning', app.folder, 'sensitive_mount', f'{service}: {src}')
            env = spec.get('environment') or []
            if 'CHANGE_ME' in json.dumps(env):
                add('warning', app.folder, 'change_me', f'{service}: configure secrets manually')
            for port in spec.get('ports') or []:
                if isinstance(port, dict) and port.get('published'):
                    protocol = str(port.get('protocol', 'tcp')).lower()
                    used_ports[(str(port['published']), protocol)].add(app.folder)
    for (port, protocol), users in used_ports.items():
        if len(users) > 1:
            add('warning', '*', 'port_collision',
                f'{port}/{protocol}: {", ".join(sorted(users))}')
    usage = image_usage(items)
    from collections import Counter
    return {'summary': {'apps': len(items), 'services': sum(len(a.source.get('services') or {}) for a in items),
                        'images': len(usage), 'errors': sum(i['level']=='error' for i in issues),
                        'warnings': sum(i['level']=='warning' for i in issues)},
            'rules': dict(sorted(Counter(i['code'] for i in issues).items())), 'findings': issues}
