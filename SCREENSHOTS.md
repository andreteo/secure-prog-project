# Unsecured baseline: screenshot and code evidence

These screenshots use local demonstration accounts and data. Pair each observed result with the relevant backend code when preparing the report.

## Baseline interface

Username-only entry page:

![[Pasted image 20261013105331.png]]

Doon's dashboard after entering a username; the address bar shows user ID `1`:

![[Pasted image 20261013105724.png]]

## Username-only sign-in and unrestricted attempts

The endpoint accepts a known username without a password and creates no authenticated session:

```python
@app.post('/api/login')
def login():
    data = request.get_json() or {}
    username = str(data.get('username', '')).strip().lower()
    user = db().execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    if user is None:
        return jsonify(error='That username does not exist.'), 404
    return jsonify(user=dict(user))
```

Repeated attempts with an unknown username continue to return HTTP 404. The console entries show multiple `/api/login` requests; this demonstrates no attempt limit in the baseline. There are no passwords to guess in this version.

![[Pasted image 20261013112515.png]]

## Cross-user dashboard access

While the interface still says “Signed in as Doon,” changing `/users/1/dashboard` to `/users/2/dashboard` displays Otherdoon's library and notes. The API uses the supplied user ID without checking it against an authenticated identity.

![[Pasted image 20261013110122.png]]

![[Pasted image 20261013110140.png]]

## Anonymous admin access

An unsigned visitor can open `/admin` and request `/api/admin/books`; both reveal records from all users.

![[Pasted image 20261013105830.png]]

![[Pasted image 20261013110457.png]]

The backend route has no authentication or administrator-role check:

```python
@app.get('/api/admin/books')
def admin_books():
    return jsonify(books=[dict(row) for row in db().execute(BOOK_SELECT + ' ORDER BY b.user_id, b.id')])
```

## Client-supplied SQL and unsafe search query

The baseline search endpoint deliberately accepts complete `UPDATE` and `SELECT` statements. Its ordinary title-search path also interpolates client input into SQL instead of binding it as a parameter:

```python
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
```

The screenshot below shows a typed `UPDATE` and a response reporting **three rows updated**, including Otherdoon's notes. Label this evidence **direct execution of client-supplied SQL with missing authorization**. The separate interpolated `LIKE` path is the classic SQL injection vulnerability; this screenshot does not demonstrate that path.

![[Pasted image 20261013112042.png]]

# Secured version: authentication and authorization evidence

## Generic login failure for an incorrect password and an unknown username

The first screenshot uses a known username with an incorrect password; the second uses an unknown username. Both receive the same generic error, so the login response does not reveal which field failed. The demo account names remain visible on the page for presentation purposes.

![[Pasted image 20261013233416.png|490]]![[Pasted image 20261013233440.png]]

## Session restoration after refresh

After refreshing the page, `/api/session` returned HTTP 200 and Doon's library reloaded without another login.

![[Pasted image 20261013234007.png]]

## Administrator endpoint denies non-admin and unsigned visitors

While signed in as a regular user, a direct request to `/api/admin/books` returns an administrator-access error and HTTP 403 Forbidden.

![[Pasted image 20261013234153.png]]![[Pasted image 20261013234300.png]]

![[Pasted image 20261013234351.png]]

After signing out, the same request returns HTTP 401 Unauthorized because there is no authenticated session.

![[Pasted image 20261013234401.png]]

## Administrator endpoint permits an administrator

The application shows the Administrator identity, and a direct request to `/api/admin/books` returns HTTP 200 with records from both users.

![[Pasted image 20261013234519.png]]
![[Pasted image 20261013234557.png]]

## Local HTTP limitation: cookie Secure flag is unset

The local demonstration runs over HTTP, so the session cookie's `Secure` flag is unset. HTTPS and a `Secure` cookie remain deployment steps; this localhost screenshot does not establish how a production deployment would behave.

![[Pasted image 20261013234700.png]]
