#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
BASELINE_DIR="$PROJECT_ROOT/.demo-baseline"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
BASELINE_PORT=${BOOKLEDGER_BASELINE_PORT:-5001}
SECURE_PORT=${BOOKLEDGER_SECURE_PORT:-5443}
cd "$PROJECT_ROOT"

if [ ! -x "$PYTHON" ] || ! command -v pnpm >/dev/null 2>&1 || \
  [ ! -x "$PROJECT_ROOT/node_modules/.bin/vite" ]; then
  echo "Install the Python and pnpm dependencies described in README.md first." >&2
  exit 1
fi
if [ ! -f instance/secure.sqlite3 ]; then
  echo "Secure demo database missing. Run: .venv/bin/python -m backend.app --init-db" >&2
  exit 1
fi
if [ ! -f local-certs/localhost.crt ] || [ ! -f local-certs/localhost.key ]; then
  echo "Local HTTPS certificate missing. See README.md for mkcert setup." >&2
  exit 1
fi
if [ "$BASELINE_PORT" = "$SECURE_PORT" ]; then
  echo "Baseline and secure ports must differ." >&2
  exit 1
fi
for port in "$BASELINE_PORT" "$SECURE_PORT"; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop the existing server before starting the comparison." >&2
    exit 1
  fi
done

if [ ! -f "$BASELINE_DIR/.prepared-v0.1.0-insecure" ]; then
  echo "Preparing the insecure baseline from Git tag v0.1.0-insecure (first run only)..."
  mkdir -p "$BASELINE_DIR"
  git archive v0.1.0-insecure | tar -xf - -C "$BASELINE_DIR"
  # Both tags use the same locked frontend packages. Share installed dependencies,
  # while keeping source files, builds and databases in separate directories.
  rm -rf "$BASELINE_DIR/node_modules"
  ln -s "$PROJECT_ROOT/node_modules" "$BASELINE_DIR/node_modules"
  (
    cd "$BASELINE_DIR"
    "$PROJECT_ROOT/node_modules/.bin/vite" build
  )
  touch "$BASELINE_DIR/.prepared-v0.1.0-insecure"
fi

# Reset only the disposable baseline database so every demonstration starts alike.
(cd "$BASELINE_DIR" && "$PYTHON" -m backend.app --reset-db)
pnpm build

baseline_pid=
secure_pid=
cleanup() {
  trap - EXIT INT TERM
  if [ -n "$secure_pid" ]; then
    kill "$secure_pid" 2>/dev/null || true
    wait "$secure_pid" 2>/dev/null || true
  fi
  if [ -n "$baseline_pid" ]; then
    kill "$baseline_pid" 2>/dev/null || true
    wait "$baseline_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

(
  cd "$BASELINE_DIR"
  exec "$PYTHON" -m backend.app --port "$BASELINE_PORT"
) &
baseline_pid=$!
"$PYTHON" -m backend.app --port "$SECURE_PORT" \
  --cert local-certs/localhost.crt --key local-certs/localhost.key &
secure_pid=$!

attempt=0
while [ "$attempt" -lt 40 ]; do
  if ! kill -0 "$baseline_pid" 2>/dev/null || ! kill -0 "$secure_pid" 2>/dev/null; then
    echo "A server stopped before the comparison was ready." >&2
    exit 1
  fi
  if curl --silent --fail --output /dev/null \
    "http://127.0.0.1:$BASELINE_PORT/api/health" && \
    curl --silent --fail --output /dev/null \
      --cacert local-certs/localhost.crt \
      "https://127.0.0.1:$SECURE_PORT/api/health"; then
    break
  fi
  attempt=$((attempt + 1))
  sleep 0.25
done
if [ "$attempt" -eq 40 ]; then
  echo "Timed out waiting for the comparison servers." >&2
  exit 1
fi

echo "Insecure baseline: http://127.0.0.1:$BASELINE_PORT"
echo "Secured version:   https://127.0.0.1:$SECURE_PORT"
if [ "${BOOKLEDGER_NO_BROWSER:-0}" != 1 ]; then
  if command -v open >/dev/null 2>&1; then
    open "http://127.0.0.1:$BASELINE_PORT"
    open "https://127.0.0.1:$SECURE_PORT"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:$BASELINE_PORT" >/dev/null 2>&1 || true
    xdg-open "https://127.0.0.1:$SECURE_PORT" >/dev/null 2>&1 || true
  fi
fi

echo "Press Ctrl+C to stop both servers. Your current Git branch is unchanged."
while kill -0 "$baseline_pid" 2>/dev/null && kill -0 "$secure_pid" 2>/dev/null; do
  sleep 1
done
echo "A comparison server stopped unexpectedly." >&2
exit 1
