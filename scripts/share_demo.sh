#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Load simple KEY=value entries without evaluating .env as shell code. Existing
# environment variables win, and only application configuration names pass.
if [[ -f "$ROOT/.env" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# || "$line" =~ ^[[:space:]]*$ ]] && continue
    if [[ "$line" =~ ^[[:space:]]*([A-Z_][A-Z0-9_]*)[[:space:]]*=(.*)$ ]]; then
      name="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"
      case "$name" in
        OPENAI_API_KEY|OPENAI_VISION_MODEL|FIRMS_MAP_KEY|MAPBOX_ACCESS_TOKEN|MAPBOX_PUBLIC_TOKEN|CAMERA_SOURCE|OPERATOR_PASSWORD|SESSION_COOKIE_SECURE|SENSOR_WEBHOOK_TOKEN|LOCAL_SMOKE_MODEL|LOCAL_SMOKE_DETECTOR|OSRM_BASE_URL) ;;
        *) continue ;;
      esac
      [[ -n "${!name:-}" ]] && continue
      value="${value%$'\r'}"
      value="${value#"${value%%[![:space:]]*}"}"
      value="${value%"${value##*[![:space:]]}"}"
      if [[ "$value" == \"*\" && "$value" == *\" ]]; then
        value="${value:1:${#value}-2}"
      elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
        value="${value:1:${#value}-2}"
      fi
      export "$name=$value"
    fi
  done < "$ROOT/.env"
fi

PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "Missing .venv. Create it and install requirements-detector-inference.txt first." >&2
  exit 1
fi
if [[ ! -f "$ROOT/models/smoke-detector.pt" ]]; then
  echo "Missing trusted model weights at models/smoke-detector.pt." >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js/npm is required to build the dashboard." >&2
  exit 1
fi
if ! command -v "${CLOUDFLARED_BIN:-cloudflared}" >/dev/null 2>&1; then
  echo "cloudflared is required for a shareable public URL. On macOS, install it with: brew install cloudflared" >&2
  exit 1
fi

PORT="${PORT:-7860}"
npm run build

TUNNEL_LOG="$(mktemp -t wildfirewatch-cloudflared.XXXXXX)"
TUNNEL_PID=""
SERVER_PID=""
TAIL_PID=""
cleanup() {
  for pid in "$SERVER_PID" "$TAIL_PID" "$TUNNEL_PID"; do
    if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; fi
  done
  rm -f "$TUNNEL_LOG"
}
trap cleanup EXIT INT TERM

"${CLOUDFLARED_BIN:-cloudflared}" tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >"$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!
ORIGIN=""
for _ in {1..45}; do
  ORIGIN="$(sed -nE 's#.*(https://[[:alnum:]-]+\.trycloudflare\.com).*#\1#p' "$TUNNEL_LOG" | head -n 1 || true)"
  # Cloudflared logs its control-plane URL (api.trycloudflare.com) before
  # allocating the random public hostname. Never mistake that endpoint for
  # the visitor URL.
  [[ "$ORIGIN" == "https://api.trycloudflare.com" ]] && ORIGIN=""
  if rg -q 'failed to request quick Tunnel|Unable to establish connection' "$TUNNEL_LOG"; then
    cat "$TUNNEL_LOG" >&2
    exit 1
  fi
  if [[ -n "$ORIGIN" ]]; then break; fi
  if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
    cat "$TUNNEL_LOG" >&2
    exit 1
  fi
  sleep 1
done
if [[ -z "$ORIGIN" ]]; then
  cat "$TUNNEL_LOG" >&2
  echo "Timed out waiting for Cloudflare to assign a public URL." >&2
  exit 1
fi

export PORT HOST=127.0.0.1 PUBLIC_ORIGIN="$ORIGIN"
export ALLOWED_ORIGINS="$ORIGIN,http://127.0.0.1:$PORT,http://localhost:$PORT"
export SESSION_COOKIE_SECURE=true
if [[ -z "${OPERATOR_PASSWORD:-}" ]]; then
  OPERATOR_PASSWORD="$(openssl rand -hex 16)"
  export OPERATOR_PASSWORD
  echo "Temporary operator password: $OPERATOR_PASSWORD"
  echo "Save it before sharing the app; the dashboard will ask for it."
fi

echo "WildfireWatch is public at: $ORIGIN"
echo "This link works only while this process and your Mac remain online. Press Ctrl-C to stop."
tail -n 8 -f "$TUNNEL_LOG" &
TAIL_PID=$!
"$PYTHON" deploy/start.py &
SERVER_PID=$!
wait "$SERVER_PID"
