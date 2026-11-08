#!/usr/bin/env bash
# The gate. Exits non-zero on any failure. Never spends Met Office quota or Gemini tokens:
# the API runs with PUBHEDGE_OFFLINE=1 (cached fixtures only, template narration).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
KIT="$ROOT/agentverse/finance/bench.py"
API_PORT=8000 WEB_PORT=3000
TMP="$(mktemp -d)"
PIDS=()
# Each background job runs in its own process group (set -m below), so killing -PID also stops uvicorn and next-server.
cleanup() { for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill -- "-$p" 2>/dev/null || true; done; }
trap cleanup EXIT
step() { printf '\n== %s\n' "$*"; }
need_free() { if lsof -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; then echo "port $1 is busy; stop the dev server first" >&2; exit 2; fi; }

step "1/6 ruff + unit tests"
uvx ruff check .
python3 -m unittest discover -s tests -q
uv run --project services/agents pytest -q services/agents/tests

step "2/6 adapter practice run (fixed seed 4242, labelled practice)"
DS="$ROOT/.bench/check-mixed-4242"
[ -d "$DS" ] || python3 "$KIT" generate --pack mixed --cases 250 --seed 4242 --output "$DS" >/dev/null
PYS=("python3")
if P39="$(uv python find 3.9 2>/dev/null)"; then PYS+=("$P39"); fi
for PY in "${PYS[@]}"; do
  OUT="$TMP/practice-$(basename "$PY")"
  (cd / && python3 "$KIT" run --dataset "$DS" --output "$OUT" --limit 250 --max-seconds 600 --adapter "$PY" "$ROOT/adapter.py" >/dev/null) || true
  python3 - "$OUT/summary.json" "$PY" "$DS/inputs.jsonl" <<'PYEOF'
import json, sys
s = json.load(open(sys.argv[1]))
markets = sum(1 for line in open(sys.argv[3]) if json.loads(line)["task"] == "markets")
f1 = s["cycle_record_metrics"]["cycle_f1"] or 0
ok = s["failed"] == 0 and s["errors"] == 0 and s["not_run"] == 0 and f1 >= 0.95 and s["strategy_runs_completed"] == markets
print(f"{sys.argv[2]}: passed={s['passed']} failed={s['failed']} errors={s['errors']} F1={f1:.3f} "
      f"markets={s['strategy_runs_completed']}/{markets} -> {'OK' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
PYEOF
done

step "3/6 front end: tsc, lint, build"
[ -d app/node_modules ] || (cd app && npm ci --silent)
(cd app && npx tsc --noEmit && npm run lint --silent && npm run build --silent >/dev/null)

step "4/6 boot services and health"
need_free $API_PORT; need_free $WEB_PORT
export PUBHEDGE_OFFLINE=1 PUBHEDGE_DB="$TMP/check.db"
set -m
(cd services/agents && uv run uvicorn pubhedge_svc.app:app --port $API_PORT >"$TMP/api.log" 2>&1) & PIDS+=($!)
(cd app && npx next start -p $WEB_PORT >"$TMP/web.log" 2>&1) & PIDS+=($!)
for i in $(seq 1 60); do curl -sf "localhost:$API_PORT/api/health" >/dev/null && curl -sf "localhost:$WEB_PORT" >/dev/null && break; sleep 1; done
curl -sf "localhost:$API_PORT/api/health" | grep -q '"offline":true'
curl -sf "localhost:$WEB_PORT" >/dev/null
echo "api + web healthy"

step "5/6 REPLAY chain run over SSE (no live API or model calls)"
curl -sN "localhost:$API_PORT/api/runs/stream?mode=replay&speed=1000" >"$TMP/replay.txt"
grep -q '"type": "done"' "$TMP/replay.txt"
! grep -q '"type": "error"' "$TMP/replay.txt"
echo "replay streamed $(grep -c '"type": "tool"' "$TMP/replay.txt") tool events"
curl -sf -XPOST "localhost:$API_PORT/api/demo/reset" >/dev/null

step "6/6 Playwright end to end"
(cd app && npx playwright install chromium >/dev/null && PW_REUSE=1 npx playwright test)
echo
echo "CHECK PASSED"
