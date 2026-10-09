"""Prevent generic SVG placeholders from shadowing verified app icons."""
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

class IconAssetTests(unittest.TestCase):
    def test_generic_icon_svg_does_not_shadow_a_real_logo(self):
        for manifest in sorted((ROOT / 'Apps').glob('*/docker-compose.yml')):
            fallback = manifest.with_name('icon.svg')
            if not fallback.is_file():
                continue
            if 'MrStore fallback icon' not in fallback.read_text(encoding='utf-8'):
                continue
            data = yaml.safe_load(manifest.read_text(encoding='utf-8'))
            icon = data['x-casaos']['icon']
            expected = f'https://raw.githubusercontent.com/mrpiracy94/MrStore/main/Apps/{manifest.parent.name}/icon.svg'
            with self.subTest(app=manifest.parent.name):
                self.assertEqual(icon, expected, 'generic SVG shadows an externally sourced icon')

if __name__ == '__main__':
    unittest.main()
