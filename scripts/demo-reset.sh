#!/usr/bin/env bash
# Reset the demo to its starting state: clears proposals, paper fills and custom limits.
# The audit log is append-only and is kept.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if curl -sf -XPOST localhost:8000/api/demo/reset >/dev/null 2>&1; then
  echo "reset via running API"
else
  uv run --project "$ROOT/services/agents" python -c "
from pubhedge_svc import audit
for t in ('proposals', 'executions', 'limits'):
    audit.db().execute(f'DELETE FROM {t}')
audit.db().commit()
print('reset database')"
fi
