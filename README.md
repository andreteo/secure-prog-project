# Book Ledger

Book Ledger is a local Secure Programming coursework demo: a React frontend, a Flask API, and a SQLite database. The secure version demonstrates password authentication, sessions, per-book ownership checks, parameterized SQL, input validation, login rate limiting, and a local HTTPS presentation mode. The deliberately insecure starting point is preserved at Git tag `v0.1.0-insecure` for the before-and-after comparison.

## Prerequisites

- Python 3 with `venv` and `pip`
- Node.js and `pnpm`
- `mkcert` if you need to generate a new locally trusted HTTPS certificate

Run all commands below from the project root.

## First-time setup

Install the backend dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Install the frontend dependencies:

```sh
pnpm install --frozen-lockfile
```

Create the secure demo database and choose passwords for `doon`, `otherdoon`, and `admin` when prompted. Each password must contain at least 12 characters:

```sh
.venv/bin/python -m backend.app --init-db
```

**Caution:** `--init-db` resets the local database, including books you added during a demo. The database is stored in `instance/secure.sqlite3`, outside the web-served directory.

## Run the frontend and backend for development

Start both servers and open the frontend with one command:

```sh
./scripts/start.sh
```

Press Ctrl+C to stop both servers. The frontend has live refresh; restart the script after backend code changes. If you want Flask's Python auto-reload, use the two-terminal commands below instead.

In terminal 1, start the Flask backend:

```sh
.venv/bin/python -m backend.app --debug
```

In terminal 2, start the React frontend through Vite:

```sh
pnpm dev
```

Open <http://127.0.0.1:5173>. Vite serves the frontend with live refresh and forwards `/api` calls to Flask at `http://127.0.0.1:5001`. Python changes restart Flask in this development mode. These development URLs use HTTP; use the HTTPS mode below when presenting the transport-security control.

If Flask reports that the secure database is missing, run the `--init-db` command from first-time setup.

## Run the HTTPS presentation

To build the frontend, start the HTTPS server, and open the app with one command (after setting up the certificate below):

```sh
./scripts/start.sh --https
```

Press Ctrl+C to stop it. The equivalent manual commands are below.

Build the React frontend first:

```sh
pnpm build
```

If `local-certs/localhost.crt` and `local-certs/localhost.key` already exist, start Flask directly:

```sh
.venv/bin/python -m backend.app --port 5443 \
  --cert local-certs/localhost.crt \
  --key local-certs/localhost.key
```

Open <https://127.0.0.1:5443>. In this mode Flask serves both the built frontend and API from the same HTTPS origin. Vite is not needed, and Flask does not allow `--debug` with the certificate options. Re-run `pnpm build` after frontend changes.

If the certificate files are missing, install `mkcert` on your computer, then generate a certificate for the two local names:

```sh
mkcert -install
mkdir -p local-certs
mkcert -cert-file local-certs/localhost.crt \
  -key-file local-certs/localhost.key localhost 127.0.0.1
```

`local-certs/` is ignored by Git. Keep the private key and live session cookies out of screenshots and commits. To check certificate validation without bypassing it, run:

```sh
curl --cacert local-certs/localhost.crt https://127.0.0.1:5443/api/health
```

This HTTPS setup is for a local presentation, not public deployment.

## Compare the insecure and secured versions

Run both versions side by side without switching Git branches:

```sh
./scripts/start_comparison.sh
```

The script extracts the tagged `v0.1.0-insecure` code into an ignored `.demo-baseline/` folder and builds it on the first run, using the project's installed frontend packages. It resets **only the baseline demo database** each time, builds the current secured frontend, and opens two local tabs:

- Insecure baseline: <http://127.0.0.1:5001> (username only)
- Secured version: <https://127.0.0.1:5443> (username and password)

Press Ctrl+C to stop both servers. If either port is already in use, stop the existing server first. The insecure copy is confined to localhost and uses synthetic data; do not expose its port to other devices.

The report draft, diagrams, and screenshot notes are in `REPORT_DRAFT.md`, `diagrams/`, and `SCREENSHOTS.md`.
