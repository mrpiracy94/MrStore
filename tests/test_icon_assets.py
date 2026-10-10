"""Prevent temporary letter-only icons from shipping in the public catalog."""
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

class IconAssetTests(unittest.TestCase):
    def test_all_local_svg_assets_are_non_generic(self):
        for fallback in sorted((ROOT / 'Apps').glob('*/icon.svg')):
            with self.subTest(app=fallback.parent.name):
                source=fallback.read_text(encoding='utf-8')
                self.assertNotIn('MrStore fallback icon',source)
                self.assertNotIn('<text',source.lower(), 'An icon containing only app initials is not acceptable')
                self.assertIn('<svg ',source)
                manifest=yaml.safe_load((fallback.parent / 'docker-compose.yml').read_text(encoding='utf-8'))
                expected=f'https://raw.githubusercontent.com/mrpiracy94/MrStore/main/Apps/{fallback.parent.name}/icon.svg'
                self.assertEqual(manifest['x-casaos']['icon'],expected)

    def test_custom_icons_are_clearly_labeled(self):
        for slug in ('budge','faster-whisper','modmanager','socket-proxy'):
            with self.subTest(app=slug):
                source=(ROOT/'Apps'/slug/'icon.svg').read_text(encoding='utf-8')
                self.assertIn('não oficial',source)
                self.assertIn('<path ',source)

    def test_every_app_has_icon_and_thumbnail(self):
        manifests=sorted((ROOT/'Apps').glob('*/docker-compose.yml'))
        self.assertEqual(len(manifests),253)
        for path in manifests:
            meta=yaml.safe_load(path.read_text(encoding='utf-8'))['x-casaos']
            with self.subTest(app=path.parent.name):
                for field in ('icon','thumbnail'):
                    self.assertTrue(meta[field].startswith('https://'),f'{field} must resolve over HTTPS')
