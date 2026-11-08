"""Polymarket public read API only (Gamma + CLOB GETs). No order, wallet or signing
endpoint is ever called: Polymarket blocks UK users from trading, so executions go to
our local paper exchange."""
import json

import httpx

from .. import cache

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
LICENCE = "Polymarket public market data (read-only API), docs.polymarket.com; not redistributed for trading"


def _get(url: str, params: dict) -> object:
    r = httpx.get(url, params=params, timeout=20, headers={"User-Agent": "pubhedge-demo/0.1"})
    r.raise_for_status()
    return r.json()


def _fetch(path: str, params: dict, base: str = GAMMA, max_age_s: float = 300) -> dict:
    assert not any(x in path for x in ("order", "auth", "trade")), "read-only client"
    key = path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return cache.fetch("polymarket", key, lambda: _get(base + path, params), source="Polymarket " +
                       ("CLOB" if base == CLOB else "Gamma"), url=base + path, licence=LICENCE, max_age_s=max_age_s)


def search(q: str) -> dict:
    return _fetch("/public-search", {"q": q, "limit_per_type": 10, "events_status": "active"})


def event(slug: str) -> dict:
    return _fetch("/events", {"slug": slug})


def price_history(token_id: str, interval: str = "1w", fidelity: int = 60) -> dict:
    return _fetch("/prices-history", {"market": token_id, "interval": interval, "fidelity": fidelity}, base=CLOB)


def book(token_id: str) -> dict:
    """Live order book for one outcome token (CLOB, read-only)."""
    return _fetch("/book", {"token_id": token_id}, base=CLOB, max_age_s=60)


def parse_market(m: dict) -> dict:
    """Flatten the fields we use; outcome arrays arrive as JSON strings."""
    tokens = json.loads(m.get("clobTokenIds") or "[]")
    prices = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
    fee = m.get("feeSchedule") or {}
    return {"slug": m.get("slug"), "question": m.get("question"), "yes_token": tokens[0] if tokens else None,
            "yes_price": prices[0] if prices else None, "best_bid": m.get("bestBid"), "best_ask": m.get("bestAsk"),
            "liquidity": float(m.get("liquidity") or 0), "volume_24h": float(m.get("volume24hr") or 0),
            "end_date": m.get("endDate"), "closed": m.get("closed"),
            "resolution_source": m.get("resolutionSource"), "fee_rate": float(fee.get("rate", 0.05))}


def taker_fee(shares: float, price: float, rate: float) -> float:
    """docs.polymarket.com/trading/fees: fee = C x feeRate x p x (1 - p), takers only."""
    return shares * rate * price * (1 - price)


def london_high_temp_event(day) -> dict:
    """Daily 'highest temperature in London' ladder, settled on London City Airport (EGLC)."""
    slug = f"highest-temperature-in-london-on-{day.strftime('%B').lower()}-{day.day}-{day.year}"
    return event(slug)
