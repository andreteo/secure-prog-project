# Local development and live refresh

The unsecured coursework baseline uses two development processes:

- Flask on `http://127.0.0.1:5001`, with Python auto-reload when `--debug` is supplied.
- Vite on `http://127.0.0.1:5173`, with browser updates when React or CSS source changes. Vite proxies `/api` requests to Flask, so open port **5173** for live frontend development.

From the project directory, start the backend in one terminal:

```sh
.venv/bin/python -m backend.app --debug
```

Start the frontend in another:

```sh
pnpm dev
```

Open [the live development site](http://127.0.0.1:5173). Edits to `src/main.jsx` refresh the frontend; CSS updates apply live. Edits to `backend/app.py` restart Flask. SQLite persists across these reloads. No rebuild is needed for frontend development.

Flask debug mode is opt-in and remains bound to localhost. The default command without `--debug` has debug mode disabled. For a built presentation version, run `pnpm build`, then `.venv/bin/python -m backend.app`, and open port 5001. That built version changes only after another build.

Restore the dummy dataset when needed (overwrites demo edits):

```sh
.venv/bin/python -m backend.app --reset-db
```

The baseline supports username-only entry for `doon`, `otherdoon`, and `admin`. Visit `/admin` to show all records without authorization. On Doon's dashboard, enter `SELECT * FROM books` in the search field to display every user's books. The original search injection input `' OR 1=1 -- ` also works. Passing baseline tests confirms these weaknesses exist; it does not establish security.

The `SELECT * FROM books` path is **direct execution of client-supplied SQL**, deliberately added for a readable presentation screenshot. It is distinct from the original SQL injection vulnerability in the search query. In the report, label the screenshot accurately and keep the typed statement and at least one `User 2` result in the frame.

To demonstrate a write through the same input, stay signed in as `doon` and enter `UPDATE books SET notes = 'Changed through SQL' WHERE id = 4`. The page reports one row updated and displays Otherdoon's altered book. Capture the statement, the update notice, and the Otherdoon book. This is **direct execution of client SQL and broken access control**, rather than a classic quote-breaking injection. The original quote-breaking search injection remains available separately. Restore the dummy data with `--reset-db` after the screenshot. The statement-prefix checks on this presentation path are not a security control.

Run the backend checks:

```sh
.venv/bin/python -m unittest discover -s tests -v
```
