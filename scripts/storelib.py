"""Shared catalog helpers. Parse YAML as data, never execute Compose files."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
VALID_CATEGORIES = {'Media', 'Productivity', 'Home', 'Networking', 'AI', 'Finance', 'Social', 'Developer', 'Others'}


def load_catalog(root=ROOT):
    root = Path(root)
    paths = sorted((root / 'Apps').glob('*/docker-compose.yml'))
    apps = {}
    for path in paths:
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError(f'{path}: Compose must be a mapping')
        apps[path.parent.name] = (data, path)
    return apps


def images_from_catalog(apps):
    usage = {}
    for app, (data, _) in apps.items():
        for service, spec in (data.get('services') or {}).items():
            image = (spec or {}).get('image')
            if isinstance(image, str):
                usage.setdefault(image, []).append(f'{app}/{service}')
    return dict(sorted(usage.items()))
