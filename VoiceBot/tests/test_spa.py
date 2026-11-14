import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.spa import FrontendFiles, is_app_page


class TestFrontendAddresses(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        dist = Path(self.folder.name)
        (dist / 'index.html').write_text('<div id="root"></div>', encoding='utf-8')
        (dist / 'assets').mkdir()
        (dist / 'assets' / 'app.js').write_text('console.log(1)', encoding='utf-8')
        app = FastAPI()

        @app.get('/api/ping')
        def ping():
            return {'ok': True}

        app.mount('/', FrontendFiles(dist), name='frontend')
        self.client = TestClient(app)

    def tearDown(self):
        self.folder.cleanup()

    def test_page_addresses_get_the_app(self):
        for path in ('/progress', '/learning-path', '/session/abc123', '/results/abc123', '/briefing?skill=negotiation'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn('id="root"', response.text)
            self.assertIn('no-cache', response.headers['cache-control'])

    def test_files_and_api_keep_working(self):
        self.assertEqual(self.client.get('/assets/app.js').text, 'console.log(1)')
        self.assertEqual(self.client.get('/api/ping').json(), {'ok': True})

    def test_unknown_addresses_and_missing_files_are_still_not_found(self):
        self.assertEqual(self.client.get('/assets/missing.js').status_code, 404)
        self.assertEqual(self.client.get('/no-such-page').status_code, 404)
        self.assertFalse(is_app_page('api/sessions'))
