#!/usr/bin/env bash
# Morning check: check.sh, then one live ping per API and one live chain run.
# Met Office is cache-first (1 h), so this spends at most one forecast call.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
"$ROOT/scripts/check.sh"
echo; echo "== live pings"
uv run --project services/agents python - <<'PYEOF'
from datetime import date
from pubhedge_svc import config
config.load_env()
from pubhedge_svc.clients import companies_house as ch, metoffice as mo, polymarket as pm, stripe_client as st, openmeteo as om
print("companies house", ch.profile("05770953")["badge"])
print("met office", mo.forecast(51.568656, -0.108575, "three-hourly")["badge"])
print("polymarket", pm.search("London")["badge"])
print("stripe", st.list_charges()["badge"])
print("open-meteo", om.daily(51.5687, -0.1086, "2026-10-01", "2026-10-07", "archive")["badge"])
from google import genai
import os
r = genai.Client(api_key=os.environ["GOOGLE_API_KEY"]).models.generate_content(model=config.MODEL_FAST, contents="say ok")
print("gemini", config.MODEL_FAST, (r.text or "").strip()[:20])
PYEOF
echo; echo "== one live chain run (live mode, this coming weekend)"
TMP="$(mktemp -d)"
(cd services/agents && PUBHEDGE_DB="$TMP/smoke.db" uv run uvicorn pubhedge_svc.app:app --port 8001 >"$TMP/api.log" 2>&1) & PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for i in $(seq 1 30); do curl -sf localhost:8001/api/health >/dev/null && break; sleep 1; done
START=$(date +%s)
curl -sN "localhost:8001/api/runs/stream?mode=live" >"$TMP/live.txt"
grep -q '"type": "done"' "$TMP/live.txt"
grep -o '"wall_ms": [0-9]*' "$TMP/live.txt" | tail -1
grep -o '"model": "[^"]*"' "$TMP/live.txt" | sort | uniq -c
echo "live run wall clock: $(( $(date +%s) - START )) s"
echo "SMOKE PASSED"
