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

This earlier Vite development screenshot runs over HTTP, so the session cookie's `Secure` flag is unset. The separate HTTPS presentation mode below should be used to show the protected cookie; neither localhost mode establishes production deployment security.

![[Pasted image 20261013234700.png]]


## Before ownership checks (`v0.1.1-auth-foundation`): changing the dashboard URL selects another user

While still signed in as Doon, changing the browser URL from `/users/1/dashboard` to `/users/3/dashboard` loads the Administrator's library. The first screenshot shows the changed URL and Doon's signed-in identity. The second shows an administrator-owned book and its private note on that page. Together, they demonstrate that a valid session is accepted for another user's records because the API trusts the user ID selected in the URL.

![[Pasted image 20261014000056.png]]

![[Pasted image 20261014000739.png]]



## After ownership checks: Doon cannot open the Administrator's library

While signed in as Doon (user ID 1), opening `/users/3/dashboard` no longer loads the Administrator's book or private note. The page displays “User not found,” and the Network panel shows HTTP 404 for both `/api/users/3` and `/api/users/3/books`. The second screenshot confirms the 404 response for `/api/users/3`; redact its session cookie value before including it in the report or repository.

![[Pasted image 20261014002638.png]]

![[Pasted image 20261014002743.png]]


## Login throttling: repeated attempts lead to HTTP 429

After repeated failed sign-in attempts, the login form shows “Too many login attempts. Try again later.” The selected Network request confirms that `POST /api/login` returned HTTP 429. The configured five-per-minute threshold and `Retry-After` response header are checked separately in `tests/test_rate_limit.py`; the header value is below the visible area of this screenshot.

![[Pasted image 20261014004359.png]]

## Book-field validation: direct API demonstration transcript

The script signs in as Doon and sends requests with a valid CSRF token against a disposable SQLite database. Invalid fields, malformed JSON, and an oversized body return HTTP 400 or 413 with all book rows unchanged; a valid book is created with HTTP 201. This is copied terminal output, not a screenshot. Use a terminal screenshot or a formatted test-results table when preparing the report.

```sh
secure_programming_project % python scripts/demo_validation.py
Book validation demo — authenticated as Doon, valid CSRF token, disposable SQLite database
POST /api/users/1/books (blank title): HTTP 400; Title must contain 1–200 characters.; database unchanged: yes
POST /api/users/1/books (client-supplied owner ID): HTTP 400; Unexpected book field.; database unchanged: yes
PUT /api/books/1 (2,001-character note): HTTP 400; Notes must contain at most 2000 characters.; database unchanged: yes
POST /api/users/1/books (malformed JSON): HTTP 400; Send book details as a JSON object.; database unchanged: yes
POST /api/users/1/books (20 KiB body): HTTP 413; Request body is too large.; database unchanged: yes
POST /api/users/1/books (valid book): HTTP 201; owner is Doon; database count increased by one
```

## HTTPS presentation: certificate validation and protected session cookie

Run the built frontend through Flask's HTTPS mode as described in `docs/DEVELOPMENT.md`. A `curl --cacert local-certs/localhost.crt` request to `/api/health` returned HTTP 200 with certificate verification result `0` on 14 October 2026. The HTTPS login response also had `Secure`, `HttpOnly`, and `SameSite=Lax` cookie attributes; the 16-test backend suite checks that HTTPS mode rejects plaintext requests. The browser screenshot below shows the HTTPS URL and cookie attributes together; the `curl` result is recorded in the test notes but has not been captured as an image.

The replacement image covers the session cookie value with an opaque block and shows the HTTPS URL and cookie flags together. A terminal capture of the `curl --cacert` result can separately show certificate validation. Do not use `curl -k` or a browser certificate-warning bypass as HTTPS evidence. Keep `local-certs/localhost.key`, live cookies, passwords, and CSRF tokens out of the report and repository.



### Local HTTPS run and protected cookie

The server output below identifies the HTTPS listener; by itself it does not prove that the browser validated the certificate.

```text
python -m backend.app --port 5443 --cert local-certs/localhost.crt --key local-certs/localhost.key
 * Serving Flask app 'app'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on https://127.0.0.1:5443
Press CTRL+C to quit
```

The local certificate was regenerated with `mkcert` for `localhost` and `127.0.0.1`. This output records the certificate names and expiry; the private key stays outside the repository.

```text
mkcert -cert-file local-certs/localhost.crt -key-file local-certs/localhost.key localhost 127.0.0.1

Created a new certificate valid for the following names 📜
 - "localhost"
 - "127.0.0.1"

The certificate is at "local-certs/localhost.crt" and the key at "local-certs/localhost.key" ✅

It will expire on 14 January 2029 🗓
```

The Safari storage panel shows the session cookie has `Secure`, `HttpOnly`, and `SameSite=Lax` set, while the address bar shows `https://127.0.0.1:5443/users/1/dashboard`. The cookie value is fully covered in this copy stored in `media/`.



![[https-secure-cookie.png]]
