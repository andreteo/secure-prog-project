"""Authentication and session checks for the secure-work branch."""
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent / 'backend'))

import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from werkzeug.security import check_password_hash
from backend.app import create_app, reset_database


PASSWORDS = {
    'doon': 'doon123456789',
    'otherdoon': 'otherdoon1234',
    'admin': 'admin12345678',
}


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / 'secure.sqlite3'
        reset_database(self.database, PASSWORDS)
        self.app = create_app(self.database)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def login(self, username='doon', password=None):
        return self.client.post('/api/login', json={
            'username': username,
            'password': PASSWORDS[username] if password is None else password,
        })

    def test_passwords_are_salted_hashes_and_never_returned(self):
        with closing(sqlite3.connect(self.database)) as db:
            hashes = [row[0] for row in db.execute('SELECT password_hash FROM users ORDER BY id')]
        self.assertEqual(len(hashes), 3)
        for username, stored in zip(PASSWORDS, hashes):
            self.assertNotIn(PASSWORDS[username], stored)
            self.assertTrue(check_password_hash(stored, PASSWORDS[username]))
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['user']['username'], 'doon')
        self.assertNotIn('password_hash', response.json['user'])
        self.assertNotIn('password_hash', self.client.get('/api/users/1').json['user'])

    def test_bad_credentials_have_same_failure_and_no_cookie(self):
        wrong = self.login(password='wrong')
        missing = self.login(username='nobody', password='wrong')
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.json, missing.json)
        self.assertEqual(wrong.json['error'], 'Username or password does not exist.')
        self.assertNotIn('Set-Cookie', wrong.headers)
        self.assertEqual(self.client.get('/api/session').status_code, 401)

    def test_cookie_session_required_and_restored(self):
        self.assertEqual(self.client.get('/api/users/1/books').status_code, 401)
        response = self.login()
        cookie = response.headers['Set-Cookie']
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Lax', cookie)
        self.assertIn('Max-Age=3600', cookie)
        self.assertEqual(self.client.get('/api/session').json['user']['id'], 1)
        self.assertEqual(self.client.get('/api/users/1/books').status_code, 200)
        self.assertEqual(self.client.get('/api/admin/books').status_code, 403)

    def test_login_rotates_session_and_logout_invalidates_it(self):
        first = self.login()
        first_cookie = first.headers['Set-Cookie'].split(';', 1)[0]
        second = self.login()
        second_cookie = second.headers['Set-Cookie'].split(';', 1)[0]
        self.assertNotEqual(first_cookie, second_cookie)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 1)
        csrf = second.json['csrf_token']
        self.assertEqual(self.client.post('/api/logout').status_code, 403)
        self.assertEqual(self.client.post('/api/logout', headers={'X-CSRF-Token': csrf}).status_code, 200)
        self.assertEqual(self.client.get('/api/session').status_code, 401)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 0)

    def test_csrf_required_for_book_mutation(self):
        csrf = self.login().json['csrf_token']
        self.assertEqual(self.client.put('/api/books/1', json={'notes': 'changed'}).status_code, 403)
        good = self.client.put('/api/books/1', json={'notes': 'changed'}, headers={'X-CSRF-Token': csrf})
        self.assertEqual(good.status_code, 200)
        self.assertEqual(good.json['book']['notes'], 'changed')

    def test_search_cannot_execute_sql_or_read_auth_tables(self):
        self.login()
        with closing(sqlite3.connect(self.database)) as db:
            before = db.execute('SELECT notes FROM books WHERE id = 4').fetchone()[0]
        for query in ('SELECT * FROM users', "' OR 1=1 -- ",
                      "UPDATE books SET notes = 'changed' WHERE id = 4"):
            response = self.client.get('/api/users/1/books', query_string={'q': query})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['books'], [])
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT notes FROM books WHERE id = 4').fetchone()[0], before)

    def test_expired_session_and_admin_role(self):
        self.login()
        with closing(sqlite3.connect(self.database)) as db:
            db.execute('UPDATE sessions SET expires_at = ?', (int(time.time()) - 1,))
            db.commit()
        self.assertEqual(self.client.get('/api/session').status_code, 401)
        self.assertEqual(self.login('admin').status_code, 200)
        self.assertEqual(self.client.get('/api/admin/books').status_code, 200)


if __name__ == '__main__':
    unittest.main()
