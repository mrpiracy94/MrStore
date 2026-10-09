"""Ensure manifest security improvements cannot silently regress."""
import re
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from catalog import apps, report
from compatibility import inspect_app

class HardenedManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.apps = {a.folder: a for a in apps()}

    def test_mandatory_secret_expressions_are_not_change_me(self):
        count = 0
        services = set()
        for app in self.apps.values():
            for name, spec in app.source['services'].items():
                env = spec.get('environment') or []
                self.assertNotIn('CHANGE_ME', str(env), f'{app.folder}/{name}')
                entries = env if isinstance(env, list) else [f'{k}={v}' for k, v in env.items()]
                for entry in entries:
                    count += len(re.findall(r'\$\{[A-Z][A-Z0-9_]*:\?[^}]+\}', str(entry)))
                    if re.search(r'\$\{[A-Z][A-Z0-9_]*:\?', str(entry)):
                        services.add((app.folder, name))
        self.assertEqual(count, 28)
        self.assertEqual(len(services), 21)
        self.assertEqual(report()['rules'].get('change_me', 0), 0)

    def test_installation_warnings_survive_builder_as_top_level_tips(self):
        from check_required_secrets import required_by_app
        required = required_by_app()
        self.assertEqual(len(required), 19)
        for name, vars in required.items():
            warning = self.apps[name].metadata.get('tips', {}).get('before_install', {})
            for locale in ('en_US', 'pt_PT'):
                self.assertIn(locale, warning, f'{name} missing {locale}')
                for variable in vars:
                    self.assertIn(variable, warning[locale], name)
            self.assertNotIn('tips', self.apps[name].source['services'].get(name, {}))

    def test_optional_docker_socket_access_removed(self):
        for app_name in ('homarr', 'homepage', 'glances', 'netdata'):
            app = self.apps[app_name]
            for service in app.source['services'].values():
                self.assertFalse(any(
                    v.get('source') == '/var/run/docker.sock'
                    for v in (service.get('volumes') or []) if isinstance(v, dict)
                ), app_name)
        remaining = [a.folder for a in self.apps.values() for spec in a.source['services'].values()
                     for v in (spec.get('volumes') or []) if isinstance(v, dict)
                     and v.get('source') == '/var/run/docker.sock']
        self.assertEqual(sorted(remaining), ['dockge', 'dozzle', 'socket-proxy'])

    def test_shared_credentials_match_across_services(self):
        immich = self.apps['immich'].source['services']
        server = next(x for x in immich['immich-server']['environment'] if x.startswith('DB_PASSWORD='))
        db = next(x for x in immich['immich-database']['environment'] if x.startswith('POSTGRES_PASSWORD='))
        self.assertEqual(server.split('=', 1)[1], db.split('=', 1)[1])
        karakeep = self.apps['karakeep'].source['services']
        app_key = next(x for x in karakeep['karakeep']['environment'] if x.startswith('MEILI_MASTER_KEY='))
        search_key = next(x for x in karakeep['karakeep-meilisearch']['environment'] if x.startswith('MEILI_MASTER_KEY='))
        self.assertEqual(app_key, search_key)

    def test_required_secrets_remain_identified_as_needing_setup(self):
        for name in ('bookstack', 'homarr', 'immich', 'karakeep', 'paperless-ngx'):
            self.assertTrue(any(x['code'] == 'required_configuration'
                                for x in inspect_app(self.apps[name])['checks']), name)

    def test_upstream_kasm_privilege_exception_is_not_hidden(self):
        self.assertIs(self.apps['kasm'].source['services']['kasm']['privileged'], True)
        self.assertEqual(report()['rules'].get('privileged'), 1)

if __name__ == '__main__':
    unittest.main()
