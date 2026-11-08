"""Stripe, test mode only. Reads the takings we seeded as test charges."""
import os

import httpx

from .. import cache

BASE = "https://api.stripe.com/v1"
LICENCE = "Stripe test mode (our own synthetic test charges)"


def _key() -> str:
    k = os.environ.get("STRIPE_SECRET_KEY", "")
    if not k.startswith("sk_test_"):
        raise PermissionError("Stripe test-mode key required")
    return k


def list_charges(limit_pages: int = 20) -> dict:
    def go():
        out, after = [], None
        for _ in range(limit_pages):
            params = {"limit": 100, **({"starting_after": after} if after else {})}
            r = httpx.get(f"{BASE}/charges", params=params, auth=(_key(), ""), timeout=30)
            r.raise_for_status()
            j = r.json()
            out += [{"id": c["id"], "amount": c["amount"], "currency": c["currency"], "livemode": c["livemode"],
                     "business_date": (c.get("metadata") or {}).get("business_date"),
                     "pub_id": (c.get("metadata") or {}).get("pub_id")} for c in j["data"]]
            if not j.get("has_more"):
                break
            after = j["data"][-1]["id"]
        return out
    return cache.fetch("stripe", "charges", go, source="Stripe test mode", url=f"{BASE}/charges",
                       licence=LICENCE, max_age_s=6 * 3600)
