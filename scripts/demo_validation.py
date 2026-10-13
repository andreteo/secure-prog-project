"""Demonstrate book validation without touching the live demo database."""

import sqlite3
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app import create_app, reset_database


def database_state(path):
    with sqlite3.connect(path) as connection:
        return tuple(connection.execute(
            'SELECT id, user_id, title, author, status, notes FROM books ORDER BY id'
        ).fetchall())


def show(label, response, expected_status, path, initial_state):
    assert response.status_code == expected_status, (label, response.status_code, response.json)
    unchanged = database_state(path) == initial_state
    assert unchanged, f'{label} unexpectedly modified the database'
    print(f'{label}: HTTP {response.status_code}; {response.json["error"]}; database unchanged: yes')


def main():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'secure.sqlite3'
        reset_database(path, {
            'doon': 'Doon-test-password-2026',
            'otherdoon': 'Otherdoon-test-password-2026',
            'admin': 'Admin-test-password-2026',
        })
        app = create_app(path)
        app.config['TESTING'] = True
        client = app.test_client()
        login = client.post('/api/login', json={
            'username': 'doon', 'password': 'Doon-test-password-2026',
        })
        assert login.status_code == 200
        headers = {'X-CSRF-Token': login.json['csrf_token']}
        initial_state = database_state(path)

        print('Book validation demo — authenticated as Doon, valid CSRF token, disposable SQLite database')
        show('POST /api/users/1/books (blank title)', client.post('/api/users/1/books', headers=headers, json={
            'title': ' ', 'author': 'Demo Author',
        }), 400, path, initial_state)
        show('POST /api/users/1/books (client-supplied owner ID)', client.post('/api/users/1/books', headers=headers, json={
            'title': 'Demo Book', 'author': 'Demo Author', 'user_id': 2,
        }), 400, path, initial_state)
        show('PUT /api/books/1 (2,001-character note)', client.put('/api/books/1', headers=headers, json={
            'notes': 'N' * 2001,
        }), 400, path, initial_state)
        show('POST /api/users/1/books (malformed JSON)', client.post('/api/users/1/books', headers=headers,
                                           data='{', content_type='application/json'),
             400, path, initial_state)
        show('POST /api/users/1/books (20 KiB body)', client.post('/api/users/1/books', headers=headers,
                                                  data='x' * 20000, content_type='application/json'),
             413, path, initial_state)

        valid = client.post('/api/users/1/books', headers=headers, json={
            'title': 'Valid Book', 'author': 'Demo Author', 'status': 'To read', 'notes': 'A short note.',
        })
        assert valid.status_code == 201
        assert valid.json['book']['user_id'] == 1
        assert len(database_state(path)) == len(initial_state) + 1
        print('POST /api/users/1/books (valid book): HTTP 201; owner is Doon; database count increased by one')


if __name__ == '__main__':
    main()
