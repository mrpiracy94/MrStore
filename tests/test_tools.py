import json
import sys
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from storelib import load_catalog, images_from_catalog
from audit_store import audit
from check_updates import check
from scan_cves import image_slice

class TestCatalog(unittest.TestCase):
    def test_store_catalog_schema(self):
        report=audit(ROOT)
        self.assertEqual(report['apps'],254)
        self.assertEqual(report['services'],260)
        self.assertEqual(report['counts'].get('error',0),0,report['findings'][:8])
    def test_image_index(self):
        images=images_from_catalog(load_catalog(ROOT))
        self.assertGreaterEqual(len(images),250)
        self.assertIn('ghcr.io/immich-app/immich-server:release',images)
    def test_shard_complete_disjoint(self):
        names=['a','b','c','d','e','f','g']
        groups=[image_slice(names,n,3) for n in range(3)]
        self.assertEqual(sorted(sum(groups,[])),sorted(names))
        for a in groups:
            for b in groups:
                if a is not b:self.assertFalse(set(a)&set(b))
    def test_digest_detects_change_and_preserves_failures(self):
        vals={'one':'sha256:'+'b'*64, 'two':None, 'three':'sha256:'+'c'*64}
        def mocked(img):return (vals[img], None if vals[img] else 'rate limited')
        state,details=check({'one':['a/s'],'two':['b/s'],'three':['c/s']},
            {'images':{'one':'sha256:'+'a'*64,'two':'sha256:'+'d'*64}},resolver=mocked,workers=2)
        self.assertEqual(len(details['changed']),1)
        self.assertEqual(len(details['new']),1)
        self.assertEqual(len(details['failed']),1)
        self.assertEqual(state['images']['two'],'sha256:'+'d'*64)

if __name__=='__main__': unittest.main()
