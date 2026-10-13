# Local development on the secure-work branch

The tagged `v0.1.0-insecure` revision preserves the original baseline and its demonstration instructions. This branch is **partway through hardening**: password authentication, server-side sessions, API sign-in checks, an admin role check, request tokens for writes, parameterized search, and plain-text note rendering are implemented. Book ownership, login throttling, and HTTPS are still pending. Do not deploy this intermediate version.

## Initialize local demo accounts

The secure version uses `instance/secure.sqlite3`, separate from the baseline database. Initialize it once:

```sh
.venv/bin/python -m backend.app --init-db
```

The command prompts for passwords of at least 12 characters for `doon`, `otherdoon`, and `admin`. It stores salted password hashes, not the passwords. For this local presentation, the login page displays the current dummy passwords; they are intentionally public demo credentials and must not be reused for real accounts or a deployment. If you reinitialize with different passwords, update or remove the login-page hint. **Running `--init-db` again replaces all secure demo data**, but does not touch `instance/baseline.sqlite3`.

## Run the site

In one terminal:

```sh
.venv/bin/python -m backend.app --debug
```

In another:

```sh
pnpm dev
```

Open <http://127.0.0.1:5173/>. Vite proxies `/api` to Flask on port 5001 and refreshes React/CSS changes live. The Flask debug option is for local development only. For a built local copy, run `pnpm build`, then start Flask without `--debug` and open port 5001.

The browser sends an opaque, HttpOnly, SameSite=Lax cookie. The server stores only its SHA-256 digest with an expiry in SQLite. On page reload, `/api/session` restores the displayed identity. Logout removes the server record and clears the cookie. The browser keeps the request token in memory; normal POST/PUT/DELETE API calls require it. The cookie is marked `Secure` on HTTPS requests, but the current localhost development site uses HTTP. HTTPS deployment and its configuration still need to be implemented and verified.

## Verify

```sh
.venv/bin/python -m unittest discover -s tests -v
pnpm build
```

The backend suite uses a disposable database and does not alter the local demo accounts. The optional browser check is `tests/browser.cjs`; it expects `BASE_URL` and `DEMO_PASSWORD` for Doon's account. It creates and removes one temporary book. The earlier baseline browser/test scripts are preserved by the `v0.1.0-insecure` tag.

Authentication alone does not establish resource ownership. Until the next hardening step, a signed-in user can still select another user ID in a URL. Do not describe this intermediate branch as a completed secure application.
