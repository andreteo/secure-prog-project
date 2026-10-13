"""Server-side book validation and unchanged-data checks."""

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


class BookValidationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / 'secure.sqlite3'
        reset_database(self.database, PASSWORDS)
        app = create_app(self.database)
        app.config['TESTING'] = True
        self.client = app.test_client()
        response = self.client.post('/api/login', json={
            'username': 'doon', 'password': PASSWORDS['doon'],
        })
        self.headers = {'X-CSRF-Token': response.json['csrf_token']}

    def book_row(self):
        with closing(sqlite3.connect(self.database)) as db:
            return db.execute(
                'SELECT title, author, status, notes FROM books WHERE id = 1'
            ).fetchone()

    def book_count(self):
        with closing(sqlite3.connect(self.database)) as db:
            return db.execute('SELECT COUNT(*) FROM books').fetchone()[0]

    def test_invalid_creates_are_rejected_without_insert(self):
        valid = {'title': 'Title', 'author': 'Author', 'status': 'To read', 'notes': 'Note'}
        invalid = [
            {},
            {**valid, 'title': '   '},
            {**valid, 'title': 123},
            {**valid, 'title': 'T' * 201},
            {**valid, 'author': ''},
            {**valid, 'author': 'A' * 201},
            {**valid, 'status': 'Unknown'},
            {**valid, 'notes': 123},
            {**valid, 'notes': 'N' * 2001},
            {**valid, 'user_id': 2},
        ]
        before = self.book_count()
        for body in invalid:
            with self.subTest(body=body):
                response = self.client.post('/api/users/1/books', json=body, headers=self.headers)
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json)
        self.assertEqual(self.book_count(), before)

    def test_malformed_json_and_oversized_body_are_rejected(self):
        before = self.book_count()
        malformed = self.client.post('/api/users/1/books', data='{',
                                     content_type='application/json', headers=self.headers)
        array = self.client.post('/api/users/1/books', json=['Title', 'Author'], headers=self.headers)
        huge = self.client.post('/api/users/1/books', data='x' * 20000,
                                content_type='application/json', headers=self.headers)
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(array.status_code, 400)
        self.assertEqual(huge.status_code, 413)
        self.assertEqual(self.book_count(), before)

    def test_invalid_updates_preserve_book_and_valid_partial_update_works(self):
        before = self.book_row()
        for body in ({'title': ''}, {'notes': 'N' * 2001}, {'status': 'Unknown'},
                     {'id': 4}, {'author': None}):
            with self.subTest(body=body):
                response = self.client.put('/api/books/1', json=body, headers=self.headers)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.book_row(), before)

        updated = self.client.put('/api/books/1', json={'notes': 'Revised note'}, headers=self.headers)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json['book']['notes'], 'Revised note')
        self.assertEqual(updated.json['book']['title'], before[0])

    def test_maximum_valid_lengths_and_defaults(self):
        response = self.client.post('/api/users/1/books', json={
            'title': 'T' * 200, 'author': 'A' * 200, 'notes': 'N' * 2000,
        }, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['book']['status'], 'To read')
        self.assertEqual(len(response.json['book']['notes']), 2000)


if __name__ == '__main__':
    unittest.main()
