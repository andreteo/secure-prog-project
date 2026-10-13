"""Resource-level authorization checks for personal libraries."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.app import create_app, reset_database


PASSWORDS = {
    'doon': 'Doon-test-password-2026',
    'otherdoon': 'Otherdoon-test-password-2026',
    'admin': 'Admin-test-password-2026',
}


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / 'secure.sqlite3'
        reset_database(self.database, PASSWORDS)
        app = create_app(self.database)
        app.config['TESTING'] = True
        self.client = app.test_client()

    def login(self, username):
        response = self.client.post('/api/login', json={
            'username': username, 'password': PASSWORDS[username],
        })
        self.assertEqual(response.status_code, 200)
        return {'X-CSRF-Token': response.json['csrf_token']}

    def test_other_users_records_cannot_be_read_or_changed(self):
        headers = self.login('doon')
        with closing(sqlite3.connect(self.database)) as db:
            before = db.execute('SELECT user_id, title, notes FROM books WHERE id = 4').fetchone()
            count = db.execute('SELECT COUNT(*) FROM books').fetchone()[0]

        for path in ('/api/users/2', '/api/users/3', '/api/users/2/books',
                     '/api/users/3/books', '/api/books/4', '/api/books/7'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

        self.assertEqual(self.client.post('/api/users/2/books', headers=headers, json={
            'title': 'Injected', 'author': 'Attacker', 'notes': 'cross-user write',
        }).status_code, 404)
        self.assertEqual(self.client.put('/api/books/4', headers=headers, json={
            'notes': 'changed',
        }).status_code, 404)
        self.assertEqual(self.client.delete('/api/books/4', headers=headers).status_code, 404)
        self.assertEqual(self.client.get('/api/admin/books').status_code, 403)

        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT user_id, title, notes FROM books WHERE id = 4').fetchone(), before)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM books').fetchone()[0], count)

    def test_owners_can_use_their_books_and_admin_has_separate_overview(self):
        headers = self.login('otherdoon')
        self.assertEqual(self.client.get('/api/users/2').json['user']['username'], 'otherdoon')
        self.assertEqual(len(self.client.get('/api/users/2/books').json['books']), 3)
        self.assertEqual(self.client.get('/api/books/4').json['book']['user_id'], 2)

        created = self.client.post('/api/users/2/books', headers=headers, json={
            'title': 'Ownership check', 'author': 'Test', 'status': 'To read', 'notes': 'private',
        })
        self.assertEqual(created.status_code, 201)
        book_id = created.json['book']['id']
        self.assertEqual(created.json['book']['user_id'], 2)
        updated = self.client.put(f'/api/books/{book_id}', headers=headers, json={
            'notes': 'updated private note',
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json['book']['notes'], 'updated private note')
        self.assertEqual(self.client.delete(f'/api/books/{book_id}', headers=headers).status_code, 204)
        self.assertEqual(self.client.get(f'/api/books/{book_id}').status_code, 404)

        self.login('admin')
        self.assertEqual(self.client.get('/api/books/1').status_code, 404)
        self.assertEqual(self.client.get('/api/books/7').status_code, 200)
        self.assertEqual(len(self.client.get('/api/admin/books').json['books']), 7)


if __name__ == '__main__':
    unittest.main()
