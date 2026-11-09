"""NFR5 and NFR8: module boundaries and protected endpoints, enforced rather than promised."""
import isolated_environment  # noqa: F401  (must come before the server)
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Each layer may import only these project layers.
ALLOWED = {
    'domain': {'domain'},
    'intelligence': {'domain', 'intelligence'},
    'modules': {'core', 'modules', 'utils', 'config', 'intelligence'},
    'services': {'domain', 'intelligence', 'services', 'core', 'utils', 'config', 'integrations'},
}
LAYERS = {'api', 'core', 'domain', 'integrations', 'intelligence', 'modules', 'services', 'utils', 'config', 'io_interfaces'}
# Recorded exceptions, each with a reason. A new one must be added here deliberately.
KNOWN = {
    ('services/structured_orchestrator.py', 'modules'): 'Reads the quota error type to wait out a brief limit.',
    ('modules/stt_router.py', 'services'): 'Reuses pure transcript comparison from recognition_quality.',
}


def project_imports(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    found = set()
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        for name in names:
            top = name.split('.')[0]
            if top in LAYERS:
                found.add(top)
    return found


class TestBoundaries(unittest.TestCase):
    def test_layers_import_only_what_they_are_allowed(self):
        problems = []
        for layer, allowed in ALLOWED.items():
            for path in (ROOT / layer).rglob('*.py'):
                relative = path.relative_to(ROOT).as_posix()
                for imported in project_imports(path) - allowed:
                    if (relative, imported) not in KNOWN:
                        problems.append(f'{relative} imports {imported}')
        self.assertEqual(problems, [])

    def test_scene_engine_has_no_provider_or_database_dependency(self):
        for name in ('scene_director', 'negotiation_strategy', 'dialogue_style', 'case_library'):
            source = (ROOT / 'intelligence' / f'{name}.py').read_text(encoding='utf-8')
            for forbidden in ('sqlite3', 'openai', 'import requests', 'fastapi'):
                self.assertNotIn(forbidden, source, f'{name} must stay independent of {forbidden}')


class TestRealDataIsSafe(unittest.TestCase):
    def test_tests_never_use_the_real_database(self):
        from api import server
        real = (ROOT / 'data' / 'hikari.db').resolve()
        self.assertNotEqual(Path(server.Config.DATABASE_PATH).resolve(), real)
        self.assertNotEqual(Path(server.training.path).resolve(), real)


class TestProtectedEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from api import server
        cls.server = server
        cls.client = TestClient(server.app)

    def test_engine_control_and_telemetry_need_a_signed_in_user(self):
        routes = [('get', '/api/monitor/snapshot', None), ('post', '/api/monitor/reset', None),
                  ('post', '/api/monitor/microphone', {'event': 'transcribed', 'device': 'Test microphone'}),
                  ('get', '/api/tts/engines', None), ('post', '/api/tts/engine', {'engine': 'kokoro'}),
                  ('post', '/api/tts/stream', {'text': 'hello'}), ('get', '/api/stt/engines', None)]
        allow = self.server.Config.ALLOW_DEMO_ACCESS
        self.server.Config.ALLOW_DEMO_ACCESS = False
        try:
            for method, path, body in routes:
                self.client.cookies.clear()
                response = getattr(self.client, method)(path, **({'json': body} if body else {}))
                self.assertEqual(response.status_code, 401, f'{method} {path} returned {response.status_code}')
        finally:
            self.server.Config.ALLOW_DEMO_ACCESS = allow


if __name__ == '__main__':
    unittest.main()
