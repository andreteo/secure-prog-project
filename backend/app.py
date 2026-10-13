"""INTENTIONALLY INSECURE. Local dummy-data teaching application only.

Weakness IDs match docs/BASELINE_DEMO.md. Flask/SQLite defaults and a few
parameterized maintenance operations do not make this application secure.
"""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / 'instance' / 'baseline.sqlite3'
BOOK_SELECT = '''SELECT b.id, b.user_id, u.username, u.display_name,
    b.title, b.author, b.status, b.notes
    FROM books b JOIN users u ON u.id = b.user_id'''


def reset_database(path):
    """Reset only this application's demo tables; never accept a remote reset."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript('''
            DROP TABLE IF EXISTS books;
            DROP TABLE IF EXISTS users;
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL
            );
            CREATE TABLE books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT ''
            );
        ''')
        db.executemany('INSERT INTO users VALUES (?, ?, ?, ?)', [
            (1, 'doon', 'Doon', 'user'),
            (2, 'otherdoon', 'Otherdoon', 'user'),
            (3, 'admin', 'Administrator', 'admin'),
        ])
        db.executemany(
            'INSERT INTO books (user_id, title, author, status, notes) VALUES (?, ?, ?, ?, ?)',
            [
                (1, 'The Left Hand of Darkness', 'Ursula K. Le Guin', 'Reading',
                 'Doon private note: revisit the discussion of trust in chapter 7.'),
                (1, 'A Room of One’s Own', 'Virginia Woolf', 'Finished',
                 'Doon private note: keep these reflections for my reading journal.'),
                (1, 'The Hobbit', 'J. R. R. Tolkien', 'To read',
                 'Doon private note: next book for the weekend.'),
                (2, 'The Dispossessed', 'Ursula K. Le Guin', 'Reading',
                 'Otherdoon private note: personal reflections on belonging.'),
                (2, 'Meditations', 'Marcus Aurelius', 'Finished',
                 'Otherdoon private note: this helped me through a difficult month.'),
                (2, 'Dune', 'Frank Herbert', 'To read',
                 'Otherdoon private note: a birthday gift idea for my sister.'),
                (3, 'The Pragmatic Programmer', 'David Thomas and Andrew Hunt', 'Reading',
                 'Admin private note: examples to revisit for the study group.'),
            ],
        )


def create_app(database_path=None):
    app = Flask(__name__, static_folder=None)
    app.config['DATABASE'] = str(database_path or DEFAULT_DB)
    if not Path(app.config['DATABASE']).exists():
        reset_database(app.config['DATABASE'])

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        connection = g.pop('db', None)
        if connection is not None:
            connection.close()

    def book_by_id(book_id):
        return db().execute(BOOK_SELECT + ' WHERE b.id = ?', (book_id,)).fetchone()

    @app.get('/api/health')
    def health():
        db().execute('SELECT 1')
        return jsonify(status='ok', stage='intentionally-insecure-baseline')

    @app.post('/api/login')
    def login():
        # V01: knowledge of a username is treated as identity. No password,
        # server session, token, or rate limit is involved.
        data = request.get_json() or {}
        username = str(data.get('username', '')).strip().lower()
        user = db().execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if user is None:
            return jsonify(error='That username does not exist.'), 404
        return jsonify(user=dict(user))

    @app.get('/api/users/<int:user_id>')
    def get_user(user_id):
        # V02: any caller can choose any user ID, including without logging in.
        user = db().execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if user is None:
            return jsonify(error='User not found.'), 404
        return jsonify(user=dict(user))

    @app.get('/api/users/<int:user_id>/books')
    def list_books(user_id):
        search = request.args.get('q', '')
        statement = search.strip()
        try:
            if statement.upper().startswith('UPDATE BOOKS SET '):
                cursor = db().execute(statement)
                db().commit()
                rows = db().execute(BOOK_SELECT + ' ORDER BY b.user_id, b.id').fetchall()
                return jsonify(books=[dict(row) for row in rows], affected_rows=cursor.rowcount)
            if statement.upper().startswith('SELECT '):
                rows = db().execute(statement).fetchall()
            else:
                sql = BOOK_SELECT + f" WHERE b.user_id = {user_id} AND b.title LIKE '%{search}%' ORDER BY b.id"
                rows = db().execute(sql).fetchall()
        except sqlite3.Error as error:
            return jsonify(error=f'Database query failed: {error}'), 400
        return jsonify(books=[dict(row) for row in rows])

    @app.get('/api/books/<int:book_id>')
    def get_book(book_id):
        row = book_by_id(book_id)
        if row is None:
            return jsonify(error='Book not found.'), 404
        return jsonify(book=dict(row))

    @app.post('/api/users/<int:user_id>/books')
    def create_book(user_id):
        data = request.get_json() or {}
        if db().execute('SELECT id FROM users WHERE id = ?', (user_id,)).fetchone() is None:
            return jsonify(error='User not found.'), 404
        # V02: the URL selects the owner; no authenticated identity is checked.
        # Bound writes keep ordinary apostrophes usable; search is the SQL demo.
        cursor = db().execute(
            'INSERT INTO books (user_id, title, author, status, notes) VALUES (?, ?, ?, ?, ?)',
            (user_id, data.get('title', ''), data.get('author', ''),
             data.get('status', 'To read'), data.get('notes', '')),
        )
        db().commit()
        return jsonify(book=dict(book_by_id(cursor.lastrowid))), 201

    @app.put('/api/books/<int:book_id>')
    def update_book(book_id):
        # V02: no ownership, role, authentication, or CSRF check.
        row = book_by_id(book_id)
        if row is None:
            return jsonify(error='Book not found.'), 404
        data = request.get_json() or {}
        db().execute(
            'UPDATE books SET title = ?, author = ?, status = ?, notes = ? WHERE id = ?',
            tuple(data.get(field, row[field]) for field in ('title', 'author', 'status', 'notes')) + (book_id,),
        )
        db().commit()
        return jsonify(book=dict(book_by_id(book_id)))

    @app.delete('/api/books/<int:book_id>')
    def delete_book(book_id):
        if book_by_id(book_id) is None:
            return jsonify(error='Book not found.'), 404
        db().execute('DELETE FROM books WHERE id = ?', (book_id,))
        db().commit()
        return '', 204

    @app.get('/api/admin/books')
    def admin_books():
        # V04: deliberately no require_authenticated_user() / require_admin().
        return jsonify(books=[dict(row) for row in db().execute(BOOK_SELECT + ' ORDER BY b.user_id, b.id')])

    @app.get('/')
    @app.get('/<path:path>')
    def frontend(path=''):
        # Serve only the built frontend, never the project root or SQLite file.
        if path.startswith('api/'):
            return jsonify(error='API endpoint not found.'), 404
        dist = ROOT / 'dist'
        if not (dist / 'index.html').exists():
            return 'Build the React frontend with pnpm build, or use the Vite dev server.', 503
        if path.startswith('assets/') or path == 'favicon.ico':
            return send_from_directory(dist, path)
        return send_from_directory(dist, 'index.html')

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset-db', action='store_true', help='Restore dummy demo data and exit.')
    parser.add_argument('--port', type=int, default=5001)
    parser.add_argument('--debug', action='store_true', help='Enable local debug mode and reload on Python changes.')
    args = parser.parse_args()
    if args.reset_db:
        reset_database(DEFAULT_DB)
        print(f'Restored dummy data in {DEFAULT_DB}')
    else:
        # Local-only containment is deliberate; this is not a public deployment.
        create_app().run(host='127.0.0.1', port=args.port, debug=args.debug)
