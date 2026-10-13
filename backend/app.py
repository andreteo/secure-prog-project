"""Local coursework app. Authentication and ownership are implemented; hardening continues."""

import argparse
import getpass
import hashlib
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from flask import Flask, g, jsonify, make_response, request, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / 'instance' / 'secure.sqlite3'
SESSION_COOKIE = 'bookledger_session'
SESSION_LIFETIME = 60 * 60
LOGIN_LIMIT = '5 per minute'
LOGIN_ERROR = 'Username or password does not exist.'
DUMMY_PASSWORD_HASH = generate_password_hash('dummy-password-for-timing')
BOOK_SELECT = '''SELECT b.id, b.user_id, u.username, u.display_name,
    b.title, b.author, b.status, b.notes
    FROM books b JOIN users u ON u.id = b.user_id'''


def reset_database(path, passwords):
    """Initialize local demo tables using passwords supplied at the terminal."""
    if set(passwords) != {'doon', 'otherdoon', 'admin'}:
        raise ValueError('Passwords are required for doon, otherdoon, and admin.')
    if any(not isinstance(value, str) or len(value) < 12 for value in passwords.values()):
        raise ValueError('Each demo password must have at least 12 characters.')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript('''
            DROP TABLE IF EXISTS sessions;
            DROP TABLE IF EXISTS books;
            DROP TABLE IF EXISTS users;
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                csrf_token TEXT NOT NULL,
                expires_at INTEGER NOT NULL
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
        db.executemany('INSERT INTO users VALUES (?, ?, ?, ?, ?)', [
            (1, 'doon', 'Doon', 'user', generate_password_hash(passwords['doon'])),
            (2, 'otherdoon', 'Otherdoon', 'user', generate_password_hash(passwords['otherdoon'])),
            (3, 'admin', 'Administrator', 'admin', generate_password_hash(passwords['admin'])),
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


def create_app(database_path=None, login_limit=LOGIN_LIMIT):
    app = Flask(__name__, static_folder=None)
    app.config['DATABASE'] = str(database_path or DEFAULT_DB)
    if not Path(app.config['DATABASE']).exists():
        raise RuntimeError('Secure database is missing. Run: python -m backend.app --init-db')

    def login_limit_response(_limit):
        return make_response(jsonify(error='Too many login attempts. Try again later.'), 429)

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        storage_uri='memory://',
        headers_enabled=True,
        retry_after='delta-seconds',
        on_breach=login_limit_response,
    )

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

    def owned_book(book_id):
        return db().execute(
            BOOK_SELECT + ' WHERE b.id = ? AND b.user_id = ?',
            (book_id, current_session()['id']),
        ).fetchone()

    def public_user(row):
        return {key: row[key] for key in ('id', 'username', 'display_name', 'role')}

    def token_hash(token):
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def current_session():
        if not hasattr(g, 'current_session'):
            token = request.cookies.get(SESSION_COOKIE, '')
            g.current_session = None
            if token:
                g.current_session = db().execute('''
                    SELECT s.token_hash, s.csrf_token, u.id, u.username, u.display_name, u.role
                    FROM sessions s JOIN users u ON u.id = s.user_id
                    WHERE s.token_hash = ? AND s.expires_at > ?
                ''', (token_hash(token), int(time.time()))).fetchone()
        return g.current_session

    @app.before_request
    def guard_api():
        if not request.path.startswith('/api/') or request.path in {'/api/login', '/api/session', '/api/health'}:
            return None
        session = current_session()
        if session is None:
            return jsonify(error='Sign in to continue.'), 401
        if request.path.startswith('/api/admin/') and session['role'] != 'admin':
            return jsonify(error='Administrator access required.'), 403
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            supplied = request.headers.get('X-CSRF-Token', '')
            if not supplied or not secrets.compare_digest(supplied, session['csrf_token']):
                return jsonify(error='Invalid request token.'), 403
        return None

    @app.after_request
    def prevent_api_caching(response):
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/health')
    def health():
        db().execute('SELECT 1')
        return jsonify(status='ok', stage='hardening-in-progress')

    @app.post('/api/login')
    @limiter.limit(login_limit)
    def login():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error=LOGIN_ERROR), 401
        username = data.get('username', '')
        password = data.get('password', '')
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 100 or len(password) > 1024:
            return jsonify(error=LOGIN_ERROR), 401
        user = db().execute('SELECT * FROM users WHERE username = ?', (username.strip().lower(),)).fetchone()
        valid = check_password_hash(user['password_hash'] if user else DUMMY_PASSWORD_HASH, password)
        if not user or not valid:
            return jsonify(error=LOGIN_ERROR), 401
        previous = request.cookies.get(SESSION_COOKIE)
        if previous:
            db().execute('DELETE FROM sessions WHERE token_hash = ?', (token_hash(previous),))
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        db().execute('INSERT INTO sessions VALUES (?, ?, ?, ?)',
                     (token_hash(token), user['id'], csrf_token, int(time.time()) + SESSION_LIFETIME))
        db().commit()
        response = jsonify(user=public_user(user), csrf_token=csrf_token)
        response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_LIFETIME,
                            secure=request.is_secure, httponly=True, samesite='Lax', path='/')
        return response

    @app.get('/api/session')
    def session_info():
        session = current_session()
        if session is None:
            return jsonify(error='Sign in to continue.'), 401
        return jsonify(user=public_user(session), csrf_token=session['csrf_token'])

    @app.post('/api/logout')
    def logout():
        db().execute('DELETE FROM sessions WHERE token_hash = ?', (current_session()['token_hash'],))
        db().commit()
        response = jsonify(status='signed-out')
        response.delete_cookie(SESSION_COOKIE, path='/', samesite='Lax')
        return response

    @app.get('/api/users/<int:user_id>')
    def get_user(user_id):
        if user_id != current_session()['id']:
            return jsonify(error='User not found.'), 404
        user = db().execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if user is None:
            return jsonify(error='User not found.'), 404
        return jsonify(user=public_user(user))

    @app.get('/api/users/<int:user_id>/books')
    def list_books(user_id):
        if user_id != current_session()['id']:
            return jsonify(error='User not found.'), 404
        search = request.args.get('q', '')
        if len(search) > 200:
            return jsonify(error='Search is too long.'), 400
        rows = db().execute(
            BOOK_SELECT + ' WHERE b.user_id = ? AND b.title LIKE ? ORDER BY b.id',
            (current_session()['id'], f'%{search}%'),
        ).fetchall()
        return jsonify(books=[dict(row) for row in rows])

    @app.get('/api/books/<int:book_id>')
    def get_book(book_id):
        row = owned_book(book_id)
        if row is None:
            return jsonify(error='Book not found.'), 404
        return jsonify(book=dict(row))

    @app.post('/api/users/<int:user_id>/books')
    def create_book(user_id):
        if user_id != current_session()['id']:
            return jsonify(error='User not found.'), 404
        data = request.get_json() or {}
        cursor = db().execute(
            'INSERT INTO books (user_id, title, author, status, notes) VALUES (?, ?, ?, ?, ?)',
            (current_session()['id'], data.get('title', ''), data.get('author', ''),
             data.get('status', 'To read'), data.get('notes', '')),
        )
        db().commit()
        return jsonify(book=dict(book_by_id(cursor.lastrowid))), 201

    @app.put('/api/books/<int:book_id>')
    def update_book(book_id):
        row = owned_book(book_id)
        if row is None:
            return jsonify(error='Book not found.'), 404
        data = request.get_json() or {}
        db().execute(
            'UPDATE books SET title = ?, author = ?, status = ?, notes = ? WHERE id = ? AND user_id = ?',
            tuple(data.get(field, row[field]) for field in ('title', 'author', 'status', 'notes'))
            + (book_id, current_session()['id']),
        )
        db().commit()
        return jsonify(book=dict(owned_book(book_id)))

    @app.delete('/api/books/<int:book_id>')
    def delete_book(book_id):
        cursor = db().execute(
            'DELETE FROM books WHERE id = ? AND user_id = ?',
            (book_id, current_session()['id']),
        )
        if cursor.rowcount == 0:
            return jsonify(error='Book not found.'), 404
        db().commit()
        return '', 204

    @app.get('/api/admin/books')
    def admin_books():
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
    parser.add_argument('--init-db', action='store_true', help='Initialize or reset the secure demo DB and prompt for passwords.')
    parser.add_argument('--port', type=int, default=5001)
    parser.add_argument('--debug', action='store_true', help='Enable local debug mode and reload on Python changes.')
    args = parser.parse_args()
    if args.init_db:
        passwords = {}
        for username in ('doon', 'otherdoon', 'admin'):
            while True:
                password = getpass.getpass(f'Password for {username} (at least 12 characters): ')
                confirm = getpass.getpass('Confirm password: ')
                if len(password) >= 12 and password == confirm:
                    passwords[username] = password
                    break
                print('Passwords must match and contain at least 12 characters.')
        reset_database(DEFAULT_DB, passwords)
        print(f'Initialized secure demo data in {DEFAULT_DB}')
    else:
        # HTTPS and production host configuration are a later hardening step.
        create_app().run(host='127.0.0.1', port=args.port, debug=args.debug)
