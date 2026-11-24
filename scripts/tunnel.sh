#!/usr/bin/env bash
# Serve the web app on a public ngrok URL so you can open it on a phone or tablet.
# Needs: ngrok signed in once (`ngrok config add-authtoken <token>`) and the API running.
# Always builds and starts its own server (never reuses one), on its own port.
set -euo pipefail

cd "$(dirname "$0")/.."
PORT="${TUNNEL_WEB_PORT:-3100}"
LOGDIR="$(mktemp -d)"

command -v ngrok >/dev/null || { echo "ngrok is not installed (brew install ngrok)"; exit 1; }
ngrok config check >/dev/null 2>&1 || { echo "ngrok is not set up: run 'ngrok config add-authtoken <token>'"; exit 1; }
if lsof -ti ":${PORT}" >/dev/null 2>&1; then
  echo "Port ${PORT} is already in use. Stop that process or set TUNNEL_WEB_PORT."; exit 1
fi

pids=()
cleanup() { for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

# Its own build folder: other `next dev` / `next build` runs must not overwrite what this serves.
export NEXT_DIST_DIR=".next-tunnel"

echo "Building the web app ..."
pnpm --filter @aitp/web build >"$LOGDIR/build.log" 2>&1 || { cat "$LOGDIR/build.log"; exit 1; }

# Run next directly (not through pnpm) so stopping the script really stops the server.
(cd apps/web && exec env NODE_ENV=production PORT="$PORT" NEXT_DIST_DIR="$NEXT_DIST_DIR" node_modules/.bin/next start) >"$LOGDIR/web.log" 2>&1 &
pids+=($!)
for _ in $(seq 1 30); do curl -fs "http://127.0.0.1:${PORT}/" >/dev/null 2>&1 && break; sleep 1; done
curl -fs "http://127.0.0.1:${PORT}/" >/dev/null 2>&1 || { echo "Web server did not start:"; cat "$LOGDIR/web.log"; exit 1; }

ngrok http "$PORT" --log=stdout --log-format=json >"$LOGDIR/ngrok.log" 2>&1 &
pids+=($!)

url=""
for _ in $(seq 1 20); do
  url=$(curl -fs http://127.0.0.1:4040/api/tunnels 2>/dev/null | PORT="$PORT" python3 -c '
import json, os, sys
for t in json.load(sys.stdin)["tunnels"]:
    if t["config"]["addr"].endswith(":" + os.environ["PORT"]):
        print(t["public_url"]); break' 2>/dev/null || true)
  [ -n "$url" ] && break
  sleep 1
done
[ -n "$url" ] || { echo "ngrok did not start; see $LOGDIR/ngrok.log"; exit 1; }

echo
echo "Open on your phone or tablet:  $url"
echo "Reachable: /, /charts, /signals, /status, and the /api health, version and live-stream endpoints. Logs: $LOGDIR"
echo "The link is public while this runs. Press Ctrl+C to stop."
# macOS ships bash 3.2 (no `wait -n`): poll until either process dies.
while kill -0 "${pids[0]}" 2>/dev/null && kill -0 "${pids[1]}" 2>/dev/null; do sleep 2; done
echo "A process exited; stopping."
