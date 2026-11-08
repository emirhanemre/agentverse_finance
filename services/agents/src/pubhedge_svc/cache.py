"""Response cache. Every real response is stored with its fetch time, so a dead API
degrades to REAL · CACHED instead of crashing."""
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .config import CACHE, RECORDED, offline


def _path(root, client: str, key: str):
    safe = hashlib.sha256(key.encode()).hexdigest()[:16]
    return root / client / f"{safe}.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read(client: str, key: str) -> Optional[dict]:
    for root in (CACHE, RECORDED):
        p = _path(root, client, key)
        if p.exists():
            return json.loads(p.read_text())
    return None


def write(client: str, key: str, env: dict, record: bool) -> None:
    for root in (CACHE,) + ((RECORDED,) if record else ()):
        p = _path(root, client, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(env, indent=1, sort_keys=True))


def fetch(client: str, key: str, fn: Callable[[], Any], *, source: str, url: str, licence: str,
          max_age_s: Optional[float] = None, record: bool = True) -> dict:
    """Return an envelope {data, badge, source, url, licence, fetched_at}.

    Fresh cache -> REAL · CACHED; else live -> REAL; live failure -> stale cache as
    REAL · CACHED; nothing at all -> raises so the caller can fall back explicitly."""
    hit = read(client, key)
    if hit and (offline() or (max_age_s is not None and time.time() - hit.get("fetched_ts", 0) < max_age_s)):
        return {**hit, "badge": "REAL · CACHED"}
    if offline():
        raise LookupError(f"offline and no cached {client} response for {key}")
    try:
        data = fn()
    except Exception as exc:  # network, auth, rate limit
        if hit:
            return {**hit, "badge": "REAL · CACHED", "live_error": type(exc).__name__}
        raise
    env = {"data": data, "source": source, "url": url, "licence": licence,
           "fetched_at": now_iso(), "fetched_ts": time.time(), "key": key}
    write(client, key, env, record)
    return {**env, "badge": "REAL"}
