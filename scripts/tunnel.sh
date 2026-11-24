#!/usr/bin/env bash
# Serve the web app on a public ngrok URL so you can open it on a phone or tablet.
# Needs: ngrok signed in once (`ngrok config add-authtoken <token>`), API running (`pnpm dev` in apps/api).
set -euo pipefail

cd "$(dirname "$0")/.."
PORT="${WEB_PORT:-3000}"

command -v ngrok >/dev/null || { echo "ngrok is not installed (brew install ngrok)"; exit 1; }
ngrok config check >/dev/null 2>&1 || { echo "ngrok is not set up: run 'ngrok config add-authtoken <token>'"; exit 1; }

pids=()
cleanup() { for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

if ! curl -fs "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
  echo "Building and starting the web app on :${PORT} ..."
  pnpm --filter @aitp/web build >/dev/null
  pnpm --filter @aitp/web start -p "$PORT" >/tmp/aitp-web.log 2>&1 &
  pids+=($!)
  for _ in $(seq 1 30); do curl -fs "http://127.0.0.1:${PORT}/" >/dev/null 2>&1 && break; sleep 1; done
fi

ngrok http "$PORT" --log=stdout --log-format=json >/tmp/aitp-ngrok.log 2>&1 &
pids+=($!)

url=""
for _ in $(seq 1 20); do
  url=$(curl -fs http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["tunnels"][0]["public_url"])' 2>/dev/null || true)
  [ -n "$url" ] && break
  sleep 1
done
[ -n "$url" ] || { echo "ngrok did not start; see /tmp/aitp-ngrok.log"; exit 1; }

echo
echo "Open on your phone or tablet:  $url"
echo "Anyone with this link can see the app while it runs. Press Ctrl+C to stop."
wait
