"""Offline regression suite: no registry access and no Docker execution."""
import json
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from catalog import apps, image_usage, report, local_asset_missing
from updates import monitor, summarize, digest
from cves import shard_images, evaluate, summarize as cve_summary, audit_exit_status
from verify_dist import verify

ONLY_AMD64 = set('audacity cura dolphin handbrake joplin modrinth mullvad-browser onlyoffice opera signal steam zotero azahar bambustudio blade-of-agony digikam dogwalk dosbox-staging eden flycast intellij-idea krita lm-studio mediaelch msedge mysql-workbench openshot pcsx2 pelorus ppsspp pycharm scummvm shadps4 shotcut webstation winegui wps-office'.split())

class StoreTests(unittest.TestCase):
    def test_every_original_app_present(self):
        self.assertEqual(len(apps()), 254)
        self.assertEqual(len({x.app_id for x in apps()}), 254)

    def test_offline_validation(self):
        audit = report()
        self.assertEqual(audit['summary']['errors'], 0, audit['findings'][:8])
        self.assertEqual(audit['summary']['services'], 260)
        self.assertEqual(audit['summary']['images'], 258)

    def test_tcp_and_udp_do_not_collide(self):
        audit = report()
        self.assertNotIn('port_collision', audit['rules'],
                         'TCP and UDP on the same numeric port are distinct bindings')

    def test_corrected_architecture(self):
        for item in apps():
            if item.folder in ONLY_AMD64:
                with self.subTest(app=item.folder):
                    self.assertEqual(item.metadata['architectures'], ['amd64'])

    def test_local_assets_exist(self):
        for app in apps():
            for field in ('icon','thumbnail'):
                with self.subTest(app=app.folder,field=field):
                    self.assertIsNone(local_asset_missing(app.metadata[field],ROOT))

    def test_local_assets_cannot_escape_repo(self):
        link='https://raw.githubusercontent.com/mrpiracy94/MrStore/main/../secrets'
        self.assertIn('unsafe', local_asset_missing(link, ROOT))

    def test_image_usage(self):
        usage=image_usage(apps())
        self.assertIn('ghcr.io/immich-app/immich-server:release',usage)
        self.assertEqual(len(usage),258)
        self.assertIn('ghcr.io/actualbudget/actual:latest', usage)
        self.assertNotIn('actualbudget/actual-server:latest', usage)

    def test_publication_uses_full_evidence_and_per_app_quarantine(self):
        import yaml
        path = ROOT / '.github' / 'workflows' / 'publish.yml'
        workflow = yaml.safe_load(path.read_text(encoding='utf-8'))
        jobs = workflow['jobs']
        scan = jobs['security_audit']
        self.assertEqual(scan['strategy']['matrix']['shard'], list(range(8)))
        self.assertFalse(scan['strategy']['fail-fast'])
        self.assertEqual(jobs['build']['needs'], 'security_audit')
        script = next(step['run'] for step in scan['steps']
                      if isinstance(step, dict) and 'run' in step
                      and 'scripts/release_scan.py' in step['run'])
        self.assertIn('--shards 8', script)
        self.assertIn('--shard', script)
        self.assertTrue(any(step.get('if') == 'always()' for step in scan['steps']))
        build = jobs['build']['steps']
        self.assertTrue(any('scripts/release_catalog.py' in str(step.get('run',''))
                            for step in build))
        builder = next(step for step in build if step.get('name') == 'Build official ZimaOS v2 catalog')
        self.assertEqual(builder['with']['source'], 'release-source')
        self.assertTrue(any('scripts/verify_dist.py' in str(step.get('run',''))
                            for step in build))
        self.assertIn('if: success()', path.read_text(encoding='utf-8'))

    def test_all_shards_are_disjoint_and_complete(self):
        keys=list(image_usage(apps()))
        batches=[shard_images(keys,idx,8) for idx in range(8)]
        self.assertEqual(sorted(sum(batches,[])),sorted(keys))
        self.assertEqual(len({item for batch in batches for item in batch}),len(keys))

    def test_registry_changes_baseline_errors(self):
        a='sha256:'+'a'*64;b='sha256:'+'b'*64;c='sha256:'+'c'*64
        answers={'update':(b,None),'error':(None,'rate limit'),'new':(c,None)}
        state,changes=monitor({'update':['a/x'],'error':['b/x'],'new':['c/x']},
                              {'images':{'update':a,'error':b}},resolver=lambda image: answers[image],workers=3)
        self.assertEqual(len(changes['changed']),1)
        self.assertEqual(len(changes['first_seen']),1)
        self.assertEqual(len(changes['failed']),1)
        self.assertEqual(state['images']['error'],b)
        self.assertNotIn('update', [x['image'] for x in changes['first_seen']])
        self.assertIn('digest',summarize(changes).lower())

    def test_transient_registry_timeout_is_retried(self):
        valid = 'sha256:' + 'a' * 64
        replies = [subprocess.TimeoutExpired('crane digest', 90),
                   subprocess.CompletedProcess('crane digest', 0, valid, '')]
        with patch('updates.subprocess.run', side_effect=replies) as runner, \
             patch('updates.time.sleep') as pause:
            result, error = digest('example/image:latest')
        self.assertEqual((result, error), (valid, None))
        self.assertEqual(runner.call_count, 2)
        pause.assert_called_once()

    def test_cve_error_is_not_clean(self):
        def mock_scan(image):
            if image=='fail':return [],'blocked'
            return ([{'severity':'CRITICAL','cve':'CVE-2026-1234','package':'library','fixed':'1.1'}],None)
        result=evaluate({'fail':['foo/bar'],'hit':['a/b']},['fail','hit'],scanner=mock_scan)
        self.assertEqual(result['failures'],1)
        self.assertEqual(result['critical'],1)
        self.assertIn('CRITICAL',cve_summary(result,0,8))
        self.assertEqual(audit_exit_status(result), 2)
        self.assertEqual(audit_exit_status({**result, 'failures': 0}), 3)
        self.assertEqual(audit_exit_status({**result, 'critical': 0, 'high': 1, 'failures': 0}), 3)
        self.assertEqual(audit_exit_status({**result, 'critical': 0, 'high': 0, 'failures': 0}), 0)


    def test_cve_registry_retries_then_returns_real_high_findings(self):
        from cves import scan
        finding = {'VulnerabilityID': 'CVE-2026-TEST', 'Severity': 'HIGH',
                   'PkgName': 'example', 'InstalledVersion': '1', 'FixedVersion': '2'}
        success = subprocess.CompletedProcess(['trivy'], 0,
            json.dumps({'Results': [{'Target': 'target', 'Vulnerabilities': [finding]}]}), '')
        blocked = subprocess.CompletedProcess(['trivy'], 1, '',
                                              'TOOMANYREQUESTS: registry rate limit')
        with patch('cves.subprocess.run', side_effect=[blocked, success]) as runner, \
             patch('cves.time.sleep') as delay:
            hits, error = scan('lscr.io/linuxserver/any:latest')
        self.assertIsNone(error)
        self.assertEqual([hit['severity'] for hit in hits], ['HIGH'])
        self.assertIn('--image-src', runner.call_args.args[0])
        self.assertEqual(runner.call_args.args[0][
            runner.call_args.args[0].index('--image-src') + 1], 'remote')
        self.assertEqual(runner.call_count, 2)
        delay.assert_called_once_with(12)

    def test_cve_scan_permanent_failure_is_not_retried_or_clean(self):
        from cves import scan
        missing = subprocess.CompletedProcess(['trivy'], 1, '', 'MANIFEST_UNKNOWN')
        with patch('cves.subprocess.run', return_value=missing) as run, \
             patch('cves.time.sleep') as wait:
            findings, error = scan('example/missing:tag')
        self.assertEqual(findings, [])
        self.assertIn('MANIFEST_UNKNOWN', error)
        run.assert_called_once()
        wait.assert_not_called()

    def test_cve_scan_exhausted_rate_limit_remains_unresolved(self):
        from cves import scan
        blocked = subprocess.CompletedProcess(['trivy'], 1, '', 'TOOMANYREQUESTS')
        with patch('cves.subprocess.run', return_value=blocked) as run, \
             patch('cves.time.sleep') as wait:
            findings, error = scan('lscr.io/linuxserver/any:latest')
        self.assertEqual(findings, [])
        self.assertIn('3/3 attempts', error)
        self.assertEqual(run.call_count, 3)
        self.assertEqual(wait.call_count, 2)

    def test_targeted_cve_rescan_cannot_drop_unknown_images(self):
        from cves import select_images
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'images.json'
            path.write_text(json.dumps(['a:v1', 'b:v1']))
            self.assertEqual(select_images({'a:v1': [], 'b:v1': [], 'c:v1': []}, path),
                             ['a:v1', 'b:v1'])
            path.write_text(json.dumps(['a:v1', 'missing:v1']))
            with self.assertRaisesRegex(ValueError, 'no longer in catalog'):
                select_images({'a:v1': []}, path)
            path.write_text(json.dumps(['a:v1', 'a:v1']))
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                select_images({'a:v1': []}, path)

    def test_inconclusive_rescan_covers_all_25_previous_failures(self):
        target = json.loads((ROOT / 'data/cve-inconclusive-20261009.json').read_text())
        self.assertEqual(len(target), 25)
        original = json.loads((ROOT / 'data/cve-inconclusive-original-20261009.json').read_text())
        self.assertEqual(len(original), 25)
        self.assertIn('lscr.io/linuxserver/netbootxyz:latest', original)
        self.assertNotIn('lscr.io/linuxserver/netbootxyz:latest', target)
        self.assertTrue(any(x.startswith('ghcr.io/mrpiracy94/mrstore-netbootxyz:') for x in target))
        self.assertEqual(len(set(target)), 25)
        self.assertTrue(set(target).issubset(image_usage(apps())))
        workflow = (ROOT / '.github/workflows/retry-inconclusive-cves.yml').read_text()
        self.assertIn('scripts/cves.py', workflow)
        self.assertIn('data/cve-inconclusive-20261009.json', workflow)
        self.assertIn('out/inconclusive-', workflow)

    def test_cve_scan_preserves_daily_audit_while_deduplicating_pushes(self):
        workflow = (ROOT / '.github/workflows/cve-scan.yml').read_text(encoding='utf-8')
        self.assertIn("group: mrstore-cve-${{ github.event_name }}-${{ github.ref }}", workflow)
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'push' }}", workflow)

    def test_legacy_qbittorrent_uses_verified_security_image(self):
        qbit = next(item for item in apps() if item.folder == 'qbittorrent-4')
        image = qbit.source['services']['qbittorrent-4']['image']
        self.assertTrue(image.startswith(
            'ghcr.io/mrpiracy94/mrstore-qbittorrent:'
            '5.2.4-libtorrentv1-secfix-20261009@sha256:'), image)
        digest = image.split('@sha256:', 1)[1]
        self.assertEqual(len(digest), 64)
        self.assertTrue(all(char in '0123456789abcdef' for char in digest))

    def test_monitor_changes_do_not_trigger_expensive_publication(self):
        publish = (ROOT / '.github/workflows/publish.yml').read_text(encoding='utf-8')
        validate = (ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8')
        self.assertNotIn("- 'scripts/**'", publish)
        for script in ('catalog.py', 'curate_taglines.py', 'validate.py', 'verify_dist.py'):
            self.assertIn(f"- 'scripts/{script}'", publish)
        self.assertIn("- 'scripts/**'", validate)

    def test_vaultwarden_alpine_keeps_catalog_ports_and_data(self):
        app = next(item for item in apps() if item.folder == 'vaultwarden')
        service = app.source['services']['vaultwarden']
        import re
        match = re.fullmatch(r'vaultwarden/server:(\d+)\.(\d+)\.(\d+)-alpine',
                             service['image'])
        self.assertIsNotNone(match, service['image'])
        self.assertGreaterEqual(tuple(map(int, match.groups())), (1, 37, 4),
                                'Do not revert upstream Vaultwarden security fixes')
        self.assertTrue(any(v.get('source') == '/DATA/AppData/vaultwarden' and
                            v.get('target') == '/data' for v in service['volumes']))
        self.assertTrue(any(p.get('target') == 80 and str(p.get('published')) == '30003'
                            for p in service['ports']))

    def test_paperless_redis_alpine_keeps_persistent_data(self):
        app = next(item for item in apps() if item.folder == 'paperless-ngx')
        service = app.source['services']['paperless-broker']
        self.assertEqual(service['image'], 'docker.io/library/redis:8.10.2-alpine')
        self.assertTrue(any(vol.get('source') == '/DATA/AppData/paperless/redis'
                            and vol.get('target') == '/data'
                            for vol in service['volumes']))
        self.assertEqual(app.source['services']['paperless-ngx']['image'],
                         'ghcr.io/paperless-ngx/paperless-ngx:latest')

    def test_karakeep_meilisearch_migration_is_explicit_and_persistent(self):
        karakeep = next(item for item in apps() if item.folder == 'karakeep')
        service = karakeep.source['services']['karakeep-meilisearch']
        self.assertEqual(service['image'], 'getmeili/meilisearch:v1.54.3@sha256:e68913ab7d6f5b159529e472cfd362ce3c741fafd3c127961b2142abbe41b3c9')
        self.assertEqual(service['command'], ['meilisearch', '--upgrade-db'])
        self.assertTrue(any(
            vol.get('source') == '/DATA/AppData/karakeep/meili' and
            vol.get('target') == '/meili_data'
            for vol in service['volumes']
        ), 'Persistent Meilisearch data must survive upgrades')

    def test_it_tools_release_is_pinned_to_scanned_multiarch_digest(self):
        it_tools = next(item for item in apps() if item.folder == 'it-tools')
        spec = it_tools.source['services']['it-tools']
        self.assertEqual(spec['image'],
                         'ghcr.io/mrpiracy94/mrstore-it-tools:'
                         'static-nginx-alpine-secfix-20261010@sha256:'
                         '36768ba51ba7fbac1f2dac8d1786c2fc7f9cf6f5afd077e677d77749d0425073')
        self.assertTrue(any(p.get('target') == 80 and str(p.get('published')) == '30013'
                            for p in spec.get('ports', [])))
        self.assertEqual(spec.get('volumes', []), [], 'IT-Tools has no persisted state')

    def test_netbootxyz_has_maintained_image_and_unchanged_network_ports(self):
        entry = next(item for item in apps() if item.folder == 'netbootxyz')
        service = entry.source['services']['netbootxyz']
        self.assertTrue(service['image'].startswith(
            'ghcr.io/mrpiracy94/mrstore-netbootxyz:2026-10-09-secfix@sha256:2a3fda1f77563529dcff6dcb0f4cbc44a48694291ca071f01995a157cc451527'), service['image'])
        self.assertEqual(set(entry.metadata['architectures']), {'amd64', 'arm64'})
        ports = {(p['target'], str(p['published']), p['protocol'])
                 for p in service['ports']}
        self.assertEqual(ports, {(3000, '20013', 'tcp'), (8080, '20014', 'tcp'),
                                 (69, '69', 'udp')})
        self.assertIn('NGINX_PORT=8080', service['environment'])
        self.assertIn('WEB_APP_PORT=3000', service['environment'])
        self.assertTrue(any(v.get('source') == '/DATA/AppData/netbootxyz/config' and
                            v.get('target') == '/config' for v in service['volumes']))
        self.assertTrue(any(v.get('source') == '/DATA/AppData/netbootxyz/assets' and
                            v.get('target') == '/assets' for v in service['volumes']))

    def test_code_server_uses_public_verified_security_image(self):
        code_server = next(a for a in apps() if a.folder == 'code-server')
        service = code_server.source['services']['code-server']
        self.assertEqual(service['image'],
                         'ghcr.io/mrpiracy94/mrstore-code-server:'
                         'lsio-node-deps-secfix-20261010@sha256:'
                         'af284b8788aeb604a86496242c23872cbdaa78e74f1b960c88fb146c984895fe')
        self.assertTrue(any(p.get('target') == 8443 and str(p.get('published')) == '20045'
                            for p in service['ports']))
        volume_paths = {(v['source'], v['target']) for v in service['volumes']}
        self.assertIn(('/DATA/AppData/code-server/config', '/config'), volume_paths)
        self.assertIn(('/DATA/Workspace', '/workspace'), volume_paths)
        self.assertIn('PUID=1000', service['environment'])
        self.assertIn('PGID=1000', service['environment'])

    def test_phpmyadmin_uses_scanned_immutable_lsio_digest(self):
        app = next(item for item in apps() if item.folder == 'phpmyadmin')
        service = app.source['services']['phpmyadmin']
        self.assertEqual(service['image'],
                         'ghcr.io/mrpiracy94/mrstore-phpmyadmin:'
                         'lsio-composer-twig-symfony-secfix-20261010@sha256:'
                         'e013e13d834b9ae5c0cf47f9edb5501aa99a60109813ef3280131621498b1749')
        self.assertTrue(any(p.get('target') == 80 and str(p.get('published')) == '20042'
                            for p in service.get('ports', [])))
        self.assertTrue(any(v.get('source') == '/DATA/AppData/phpmyadmin/config'
                            and v.get('target') == '/config' for v in service['volumes']))
        for env in ('PUID=1000', 'PGID=1000', 'PMA_ARBITRARY=1'):
            self.assertIn(env, service['environment'])

    def test_frigate_defaults_are_not_privileged(self):
        frigate = next(item for item in apps() if item.folder == 'frigate')
        self.assertIsNot(frigate.source['services']['frigate'].get('privileged'), True)

    def test_generated_store_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); app=root/'apps'/'io.github.example.sample';app.mkdir(parents=True)
            (root/'store.json').write_text('{"version":2}')
            (root/'index.json').write_text(json.dumps({'version':2,'app_count':1,'apps':[{'id':'io.github.example.sample','version':'1.0.0','content_hash':'abc123ab','compose_url':'/apps/io.github.example.sample/docker-compose.yml','meta_url':'/apps/io.github.example.sample/meta.json','icon':'https://example.org/icon.svg'}]}))
            (app/'meta.json').write_text('{}')
            (app/'docker-compose.yml').write_text('services: {}')
            self.assertEqual(verify(root,1),1)
            with self.assertRaisesRegex(ValueError,'Expected 2 apps'):
                verify(root,2)

if __name__=='__main__':unittest.main()
