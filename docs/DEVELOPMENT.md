# Local development on the secure-work branch

The tagged `v0.1.0-insecure` revision preserves the original baseline and its demonstration instructions. The `v0.1.1-auth-foundation` tag captures the intermediate version before ownership checks. This branch implements password authentication, server-side sessions, API sign-in checks, an admin role check, book ownership, request tokens for writes, parameterized search, plain-text note rendering, login throttling, book-field validation, and a **localhost HTTPS demonstration**. It is not a production deployment.

## Initialize local demo accounts

The secure version uses `instance/secure.sqlite3`, separate from the baseline database. Initialize it once:

```sh
.venv/bin/python -m backend.app --init-db
```

The command prompts for passwords of at least 12 characters for `doon`, `otherdoon`, and `admin`. It stores salted password hashes, not the passwords. For this local presentation, the login page displays the current dummy passwords; they are intentionally public demo credentials and must not be reused for real accounts or a deployment. If you reinitialize with different passwords, update or remove the login-page hint. **Running `--init-db` again replaces all secure demo data**, but does not touch `instance/baseline.sqlite3`.

## Run the site

Install the pinned Python dependencies after pulling this version:

```sh
python -m pip install -r requirements.txt
```

In one terminal:

```sh
.venv/bin/python -m backend.app --debug
```

In another:

```sh
pnpm dev
```

Open <http://127.0.0.1:5173/>. Vite proxies `/api` to Flask on port 5001 and refreshes React/CSS changes live. The Flask debug option is for local development only. For a built local copy, run `pnpm build`, then start Flask without `--debug` and open port 5001.

The browser sends an opaque, HttpOnly, SameSite=Lax cookie. The server stores only its SHA-256 digest with an expiry in SQLite. On page reload, `/api/session` restores the displayed identity. Logout removes the server record and clears the cookie. The browser keeps the request token in memory; normal POST/PUT/DELETE API calls require it. The HTTP/Vite workflow above is for development; its cookie is not `Secure`.

## HTTPS presentation mode

Build the frontend, then create a disposable localhost certificate and start Flask directly over TLS:

```sh
pnpm build
sh scripts/create_local_cert.sh
.venv/bin/python -m backend.app --port 5443 --cert local-certs/localhost.crt --key local-certs/localhost.key
```

Open <https://127.0.0.1:5443/>. The certificate generator uses OpenSSL, gives the certificate `localhost` and `127.0.0.1` subject alternative names, and keeps the private key in ignored `local-certs/` with owner-only permissions. It refuses to overwrite an existing certificate; remove both generated files before regenerating. The certificate expires after 30 days. **A self-signed certificate is not automatically trusted by the browser.** For a browser screenshot without a warning, replace it with a locally trusted certificate. On macOS, [mkcert's official instructions](https://github.com/FiloSottile/mkcert) provide this route:

```sh
brew install mkcert
mkcert -install
umask 077
mkcert -cert-file local-certs/localhost.crt -key-file local-certs/localhost.key localhost 127.0.0.1
```

Restart the Flask HTTPS server after replacing the certificate. `mkcert -install` adds a local certificate authority to your machine's trust store; do this only on a machine you control, and never share its root CA private key. Firefox may need the additional NSS setup described by mkcert. Do not treat a browser warning bypass as certificate validation. Keep the server private key private and never commit it.

For a command-line check without changing system trust, validate against the generated certificate:

```sh
curl --cacert local-certs/localhost.crt -o /dev/null -w 'HTTP %{http_code}; certificate check %{ssl_verify_result}\n' https://127.0.0.1:5443/api/health
```

Expect HTTP 200 and certificate check `0`; do not use `curl -k`. The command with `--cacert` validates the certificate explicitly whether it came from OpenSSL or mkcert. In this mode Flask serves both the built frontend and `/api` on the same HTTPS origin, requires HTTPS for every request, restricts Host to `localhost` or `127.0.0.1`, disables debug mode, and sets the session cookie's `Secure` flag. The separate Vite development server remains HTTP, so use port 5443 for the HTTPS screenshot and confirm the browser address bar shows `https://` without a certificate warning. Capture the login response's cookie *attributes* only; redact its value and the CSRF token. The local Flask server is a development server and is **not suitable for production**. A real deployment needs a production web server/TLS setup, a certificate trusted for its public hostname, and shared limiter storage if multiple workers are used.

## Login throttling policy

`/api/login` accepts at most five requests per minute from each client IP address. Both successful and failed requests count. A sixth request returns HTTP 429 with a generic JSON error and a `Retry-After` header; the response does not create a session. The counter is kept in Flask-Limiter's in-memory store, so it resets on server restart and is not shared between workers. This is suitable for the single-process local demonstration, but a deployed multi-worker service needs shared limiter storage. The app uses the directly connected IP address and does not trust forwarded IP headers; deployment behind a proxy requires an explicit trusted-proxy configuration. This control slows repeated login guesses at the application endpoint; it does not prevent distributed guessing or network-level denial of service. The demo test waits for a short configured window; the running application uses one minute.

For a report screenshot, restart the local Flask server to clear the demonstration counter, submit five incorrect passwords from the same browser, then capture the sixth login request showing HTTP 429 and `Retry-After` in Network. Keep session cookies and request tokens out of shared screenshots.

## Book-field validation

The backend requires a JSON object for book creation and updates. Title and author must each be nonblank strings of at most 200 characters; status must be `To read`, `Reading`, or `Finished`; notes must be a string of at most 2,000 characters. Create defaults omitted status to `To read` and omitted notes to empty text. Updates can supply only the fields being changed. Unexpected fields, including a client-supplied `user_id`, are rejected. Malformed or invalid book data returns HTTP 400; request bodies above 16 KiB return HTTP 413. The React form sends only editable fields and mirrors the length limits, but the backend applies the checks to direct API requests as well. Tests verify rejected requests leave the SQLite rows unchanged.

For a presentation-friendly direct API demonstration, run this from the project root:

```sh
python scripts/demo_validation.py
```

`python -m scripts.demo_validation` works too.

The script creates a temporary SQLite database, signs in with a dummy account, sends requests with a valid CSRF token, and prints each response alongside whether rejected requests changed the data. It also shows a valid book creation succeeding. It does not contact the running development server or alter your local demo library. Screenshot the terminal output and cite `scripts/demo_validation.py` and `tests/test_validation.py` in the report; the frontend's HTML field limits alone are not evidence of server validation.

## Verify

Run these commands from the project root (`secure_programming_project`), not from `tests/`. If your terminal is currently in `tests/`, run `cd ..` first. The tests import `backend.app` as a project package.

```sh
.venv/bin/python -m unittest discover -s tests -v
pnpm build
```

The backend suite uses a disposable database and does not alter the local demo accounts. The optional browser check is `tests/browser.cjs`; it expects `BASE_URL` and `DEMO_PASSWORD` for Doon's account. It creates and removes one temporary book. The earlier baseline browser/test scripts are preserved by the `v0.1.0-insecure` tag.

Personal API routes require the URL user ID or book owner to match the authenticated user. Cross-user requests return 404, including reads, creation, updates, and deletion; the separate administrator overview still requires the admin role. The ownership suite checks that rejected writes leave stored records unchanged and that legitimate owner operations continue to work. The HTTPS test checks plaintext rejection and cookie flags; the separate `curl --cacert` command verifies a real TLS connection. The localhost certificate is not a public deployment certificate.
