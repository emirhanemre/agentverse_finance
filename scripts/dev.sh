#!/usr/bin/env bash
# Start the agent service (port 8000) and the front end (port 3000). Ctrl-C stops both.
# Set PUBHEDGE_OFFLINE=1 to run without any live API or model calls.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -d "$ROOT/app/node_modules" ] || (cd "$ROOT/app" && npm install)
(cd "$ROOT/services/agents" && uv run uvicorn pubhedge_svc.app:app --port 8000 --reload) & API=$!
trap 'kill $API 2>/dev/null || true' EXIT
cd "$ROOT/app" && npm run dev
