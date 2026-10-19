#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
cd "$PROJECT_ROOT"

mode=${1:-dev}
case "$mode" in
  dev|--https) ;;
  *)
    echo "Usage: ./scripts/start.sh [--https]" >&2
    exit 2
    ;;
esac

if [ ! -x .venv/bin/python ]; then
  echo "Python environment missing. Run: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt" >&2
  exit 1
fi
if [ ! -f instance/secure.sqlite3 ]; then
  echo "Demo database missing. Run: .venv/bin/python -m backend.app --init-db" >&2
  exit 1
fi

backend_pid=
frontend_pid=
cleanup() {
  trap - EXIT INT TERM
  if [ -n "$frontend_pid" ]; then
    kill "$frontend_pid" 2>/dev/null || true
    wait "$frontend_pid" 2>/dev/null || true
  fi
  if [ -n "$backend_pid" ]; then
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

wait_for_server() {
  pid=$1
  url=$2
  attempt=0
  while [ "$attempt" -lt 40 ]; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "Server stopped before it became ready: $url" >&2
      return 1
    fi
    if curl --silent --fail --output /dev/null "$url"; then
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 0.25
  done
  echo "Timed out waiting for $url" >&2
  return 1
}

open_browser() {
  url=$1
  echo "Open $url"
  if [ "${BOOKLEDGER_NO_BROWSER:-0}" != 1 ]; then
    if command -v open >/dev/null 2>&1; then
      open "$url"
    elif command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$url" >/dev/null 2>&1 || true
    fi
  fi
}

if [ "$mode" = --https ]; then
  if ! command -v pnpm >/dev/null 2>&1; then
    echo "pnpm is required to build the frontend." >&2
    exit 1
  fi
  if [ ! -f local-certs/localhost.crt ] || [ ! -f local-certs/localhost.key ]; then
    echo "Local HTTPS certificate missing. See README.md for mkcert setup." >&2
    exit 1
  fi
  pnpm build
  .venv/bin/python -m backend.app --port 5443 \
    --cert local-certs/localhost.crt \
    --key local-certs/localhost.key &
  backend_pid=$!
  attempt=0
  while [ "$attempt" -lt 40 ]; do
    if ! kill -0 "$backend_pid" 2>/dev/null; then
      echo "HTTPS server stopped before it became ready." >&2
      exit 1
    fi
    if curl --silent --fail --output /dev/null \
      --cacert local-certs/localhost.crt https://127.0.0.1:5443/api/health; then
      break
    fi
    attempt=$((attempt + 1))
    sleep 0.25
  done
  if [ "$attempt" -eq 40 ]; then
    echo "Timed out waiting for the HTTPS server." >&2
    exit 1
  fi
  open_browser https://127.0.0.1:5443
else
  if [ ! -x node_modules/.bin/vite ]; then
    echo "Frontend dependencies missing. Run: pnpm install --frozen-lockfile" >&2
    exit 1
  fi
  .venv/bin/python -m backend.app &
  backend_pid=$!
  wait_for_server "$backend_pid" http://127.0.0.1:5001/api/health

  node_modules/.bin/vite --host 127.0.0.1 --port 5173 --strictPort &
  frontend_pid=$!
  wait_for_server "$frontend_pid" http://127.0.0.1:5173/
  open_browser http://127.0.0.1:5173
fi

echo "Press Ctrl+C to stop the server(s)."
while kill -0 "$backend_pid" 2>/dev/null && \
  { [ -z "$frontend_pid" ] || kill -0 "$frontend_pid" 2>/dev/null; }; do
  sleep 1
done
echo "A server stopped unexpectedly." >&2
exit 1
