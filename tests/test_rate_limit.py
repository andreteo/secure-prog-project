"""Login throttling and recovery checks using disposable demo data."""

import tempfile
import time
import unittest
from pathlib import Path

from backend.app import create_app, reset_database


PASSWORDS = {
    'doon': 'Doon-test-password-2026',
    'otherdoon': 'Otherdoon-test-password-2026',
    'admin': 'Admin-test-password-2026',
}


class LoginRateLimitTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / 'secure.sqlite3'
        reset_database(self.database, PASSWORDS)

    def client(self, limit='5 per minute'):
        app = create_app(self.database, login_limit=limit)
        app.config['TESTING'] = True
        return app.test_client()

    def login(self, client, password, address='198.51.100.10'):
        return client.post('/api/login', json={
            'username': 'doon', 'password': password,
        }, environ_overrides={'REMOTE_ADDR': address})

    def test_sixth_request_is_limited_before_password_check(self):
        client = self.client()
        for _ in range(5):
            self.assertEqual(self.login(client, 'wrong').status_code, 401)
        limited = self.login(client, PASSWORDS['doon'])
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json['error'], 'Too many login attempts. Try again later.')
        self.assertGreater(int(limited.headers['Retry-After']), 0)
        self.assertEqual(limited.headers['X-RateLimit-Limit'], '5')
        self.assertNotIn('Set-Cookie', limited.headers)
        self.assertEqual(self.login(client, PASSWORDS['doon'], '198.51.100.11').status_code, 200)

    def test_login_is_available_after_window_expires(self):
        client = self.client('1 per second')
        self.assertEqual(self.login(client, 'wrong').status_code, 401)
        self.assertEqual(self.login(client, PASSWORDS['doon']).status_code, 429)
        time.sleep(1.2)
        self.assertEqual(self.login(client, PASSWORDS['doon']).status_code, 200)


if __name__ == '__main__':
    unittest.main()
