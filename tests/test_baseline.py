"""Characterize the INSECURE baseline, including expected vulnerabilities.

Passing here means baseline behaviour is reproduced, NOT that it is secure.
Tests use a disposable database and do not alter the presentation dataset.
"""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.app import create_app, reset_database


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / 'test.sqlite3'
        self.app = create_app(self.database)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_username_only_login_has_no_session(self):
        response = self.client.post('/api/login', json={'username': 'doon'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['user']['id'], 1)
        self.assertNotIn('Set-Cookie', response.headers)
        self.assertEqual(self.client.post('/api/login', json={'username': 'missing'}).status_code, 404)

    def test_valid_search_limits_results_to_requested_user(self):
        response = self.client.get('/api/users/1/books', query_string={'q': 'Hobbit'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([b['title'] for b in response.json['books']], ['The Hobbit'])
        self.assertEqual(self.client.get('/api/users/1/books', query_string={'q': 'no-match'}).json['books'], [])

    def test_book_crud_persists_and_accepts_apostrophes(self):
        book = dict(title="Reader's choice", author="O'Connor", status='To read', notes='A private note.')
        response = self.client.post('/api/users/1/books', json=book)
        self.assertEqual(response.status_code, 201)
        book_id = response.json['book']['id']
        updated = self.client.put(f'/api/books/{book_id}', json={'status': 'Finished'})
        self.assertEqual(updated.json['book']['status'], 'Finished')
        self.assertEqual(self.client.get(f'/api/books/{book_id}').json['book']['title'], book['title'])
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT status FROM books WHERE id=?', (book_id,)).fetchone()[0], 'Finished')
        self.assertEqual(self.client.delete(f'/api/books/{book_id}').status_code, 204)
        self.assertEqual(self.client.get(f'/api/books/{book_id}').status_code, 404)

    def test_v02_cross_user_read_update_and_delete_are_unprotected(self):
        self.client.post('/api/login', json={'username': 'doon'})
        books = self.client.get('/api/users/2/books').json['books']
        self.assertEqual(len(books), 3)
        self.assertTrue(all(b['username'] == 'otherdoon' for b in books))
        book_id = books[0]['id']
        self.assertEqual(self.client.put(f'/api/books/{book_id}', json={'notes': 'Changed by Doon'}).status_code, 200)
        self.assertEqual(self.client.get(f'/api/books/{book_id}').json['book']['notes'], 'Changed by Doon')
        self.assertEqual(self.client.delete(f'/api/books/{book_id}').status_code, 204)

    def test_v03_search_sql_injection_exposes_other_users(self):
        normal = self.client.get('/api/users/1/books').json['books']
        response = self.client.get('/api/users/1/books', query_string={'q': "' OR 1=1 -- "})
        self.assertEqual(response.status_code, 200)
        exposed = response.json['books']
        self.assertEqual(len(normal), 3)
        self.assertEqual(len(exposed), 7)
        self.assertEqual({b['username'] for b in exposed}, {'doon', 'otherdoon', 'admin'})

    def test_v03_direct_select_returns_all_books(self):
        response = self.client.get('/api/users/1/books', query_string={'q': 'SELECT * FROM books'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['books']), 7)
        self.assertEqual({b['user_id'] for b in response.json['books']}, {1, 2, 3})

    def test_v03_direct_update_changes_other_users_book(self):
        original = self.client.get('/api/books/4').json['book']['notes']
        statement = "UPDATE books SET notes = 'Changed through SQL' WHERE id = 4"
        response = self.client.get('/api/users/1/books', query_string={'q': statement})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['affected_rows'], 1)
        self.assertEqual(self.client.get('/api/books/4').json['book']['notes'], 'Changed through SQL')
        self.assertEqual(self.client.get('/api/books/1').json['book']['user_id'], 1)
        self.assertNotEqual(original, 'Changed through SQL')

    def test_v04_anonymous_admin_api_exposes_private_notes(self):
        response = self.client.get('/api/admin/books')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['books']), 7)
        self.assertTrue(any('Otherdoon private note' in b['notes'] for b in response.json['books']))

    def test_repeated_login_attempts_are_not_limited(self):
        responses = [self.client.post('/api/login', json={'username': 'missing'}) for _ in range(10)]
        self.assertEqual([r.status_code for r in responses], [404] * 10)

    def test_v05_raw_html_notes_are_stored_without_sanitization(self):
        payload = '<b>HTML demonstration</b>'
        self.client.put('/api/books/1', json={'notes': payload})
        self.assertEqual(self.client.get('/api/books/1').json['book']['notes'], payload)

    def test_v06_bad_search_returns_database_error(self):
        response = self.client.get('/api/users/1/books', query_string={'q': "'"})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Database query failed', response.json['error'])

    def test_reset_restores_seed_data(self):
        self.client.delete('/api/books/1')
        reset_database(self.database)
        self.assertEqual(len(self.client.get('/api/admin/books').json['books']), 7)
        self.assertEqual(self.client.get('/api/books/1').json['book']['title'], 'The Left Hand of Darkness')


if __name__ == '__main__':
    unittest.main(verbosity=2)
