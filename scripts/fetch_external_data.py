#!/usr/bin/env python3
"""Fetch real Polymarket public market data (Gamma + CLOB) and real historical London weather data (Open-Meteo).

Uses only public read-only endpoints. Requires no API keys or wallet credentials.
Saves authentic responses with retrieval timestamps for reproducible offline inspection and replay.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any
import requests

ROOT = Path(__file__).resolve().parent.parent
POLYMARKET_CACHE_DIR = ROOT / "data" / "polymarket_cache"
RAW_DATA_DIR = ROOT / "data" / "raw"

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def parse_json_field(val: Any) -> list[Any]:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, TypeError):
            pass
    return []


def iso_to_unix(iso_str: str | None) -> int | None:
    if not iso_str:
        return None
    try:
        cleaned = iso_str.replace("Z", "+00:00")
        return int(dt.datetime.fromisoformat(cleaned).timestamp())
    except ValueError:
        return None


def fetch_clob_book(session: requests.Session, token_id: str) -> dict[str, Any] | None:
    url = f"{CLOB_BASE}/book"
    try:
        resp = session.get(url, params={"token_id": token_id}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and ("bids" in data or "asks" in data):
                return {
                    "source_url": f"{url}?token_id={token_id}",
                    "retrieved_at": utc_now_iso(),
                    "bids": data.get("bids", [])[:15],
                    "asks": data.get("asks", [])[:15],
                    "market": data.get("market"),
                    "asset_id": data.get("asset_id", token_id),
                    "timestamp": data.get("timestamp"),
                }
    except requests.RequestException:
        pass
    return None


def fetch_clob_price_history(
    session: requests.Session,
    token_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any] | None:
    url = f"{CLOB_BASE}/prices-history"
    start_ts = iso_to_unix(start_date)
    end_ts = iso_to_unix(end_date)

    param_attempts: list[dict[str, Any]] = []
    if start_ts and end_ts:
        param_attempts.append(
            {
                "market": token_id,
                "startTs": start_ts - 86400,
                "endTs": end_ts + 86400,
                "fidelity": 60,
            }
        )
    param_attempts.append({"market": token_id, "interval": "max", "fidelity": 60})
    param_attempts.append({"market": token_id, "interval": "1w", "fidelity": 60})

    for params in param_attempts:
        try:
            resp = session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                history = data.get("history", [])
                if history:
                    return {
                        "source_url": resp.url,
                        "retrieved_at": utc_now_iso(),
                        "point_count": len(history),
                        "history_sample": history[-50:] if len(history) > 50 else history,
                    }
        except requests.RequestException:
            pass
    return None


def is_weather_or_uk_relevant(market: dict[str, Any]) -> tuple[bool, list[str]]:
    question = str(market.get("question", "")).lower()
    desc = str(market.get("description", "")).lower()
    slug = str(market.get("slug", "")).lower()
    combined = f"{question} {desc} {slug}"

    weather_terms = [
        "temperature",
        "highest temperature",
        "rainfall",
        "rain",
        "precipitation",
        "weather",
        "celsius",
        "fahrenheit",
        "°c",
        "°f",
        "hottest",
        "warmest",
        "snow",
        "inch of rain",
        "mm of rain",
        "met office",
        "wunderground",
        "national weather service",
        "noaa",
        "hurricane",
    ]
    uk_terms = [
        "london",
        "united kingdom",
        "uk ",
        "heathrow",
        "england",
        "britain",
    ]

    matched_tags: list[str] = []
    for t in weather_terms:
        if t in combined:
            matched_tags.append(f"weather:{t.strip()}")
    for t in uk_terms:
        if t in combined:
            matched_tags.append(f"location:{t.strip()}")

    return (len(matched_tags) > 0, matched_tags)


def infer_structured_metadata(raw: dict[str, Any], tags: list[str]) -> dict[str, Any]:
    question = str(raw.get("question", ""))
    desc = str(raw.get("description", ""))
    combined = f"{question} {desc}".lower()

    location = "Unspecified / Global"
    if "london" in combined:
        location = "London, UK (London City Airport EGLC)" if "eglc" in combined else "London, UK"
    elif "new york" in combined or "nyc" in combined or "central park" in combined:
        location = "New York City, US"
    elif "seoul" in combined:
        location = "Seoul, South Korea"
    elif "chicago" in combined:
        location = "Chicago, US"
    elif "united kingdom" in combined or " uk " in combined:
        location = "United Kingdom"

    measurement = "non_weather_event"
    if "highest temperature" in combined or "temperature" in combined or "hottest" in combined:
        measurement = "daily_max_temperature" if "highest temperature" in combined else "temperature"
    elif "rainfall" in combined or "precipitation" in combined or "rain" in combined:
        measurement = "precipitation_or_rainfall"
    elif "hurricane" in combined:
        measurement = "storm_or_hurricane"

    resolution_source = str(raw.get("resolutionSource", "")).strip()
    if not resolution_source:
        if "wunderground" in combined:
            resolution_source = "Weather Underground (https://www.wunderground.com/history/daily/gb/london/EGLC)" if "eglc" in combined else "Weather Underground"
        elif "noaa" in combined:
            resolution_source = "NOAA / National Weather Service"
        elif "met office" in combined:
            resolution_source = "UK Met Office"
        else:
            resolution_source = "Polymarket Official Resolution Rules"

    return {
        "inferred_location": location,
        "inferred_measurement": measurement,
        "inferred_resolution_source": resolution_source,
    }


def normalize_market_record(
    session: requests.Session,
    raw: dict[str, Any],
    matched_tags: list[str],
    fetch_clob: bool = True,
) -> dict[str, Any]:
    market_id = str(raw.get("id", ""))
    slug = str(raw.get("slug", ""))
    outcomes = [str(x) for x in parse_json_field(raw.get("outcomes"))]
    outcome_prices = [str(x) for x in parse_json_field(raw.get("outcomePrices"))]
    clob_token_ids = [str(x) for x in parse_json_field(raw.get("clobTokenIds"))]
    start_date = raw.get("startDate")
    end_date = raw.get("endDate")
    is_closed = bool(raw.get("closed", False))

    order_books: dict[str, Any] = {}
    price_histories: dict[str, Any] = {}

    if fetch_clob and clob_token_ids:
        for idx, token_id in enumerate(clob_token_ids[:2]):
            label = outcomes[idx] if idx < len(outcomes) else f"outcome_{idx}"
            if not is_closed:
                book = fetch_clob_book(session, token_id)
                if book is not None:
                    order_books[label] = book
            hist = fetch_clob_price_history(session, token_id, start_date=start_date, end_date=end_date)
            if hist is not None and hist.get("point_count", 0) > 0:
                price_histories[label] = hist

    meta = infer_structured_metadata(raw, matched_tags)

    return {
        "market_id": market_id,
        "condition_id": str(raw.get("conditionId", "")),
        "slug": slug,
        "source_url": f"https://polymarket.com/event/{slug}" if slug else f"{GAMMA_BASE}/markets/{market_id}",
        "gamma_api_url": f"{GAMMA_BASE}/markets/{market_id}",
        "retrieval_timestamp": utc_now_iso(),
        "question": str(raw.get("question", "")),
        "resolution_rules": str(raw.get("description", "")),
        "resolution_source": meta["inferred_resolution_source"],
        "location": meta["inferred_location"],
        "measurement": meta["inferred_measurement"],
        "outcomes": outcomes,
        "outcome_prices": outcome_prices,
        "clob_token_ids": clob_token_ids,
        "start_date": start_date,
        "end_date": end_date,
        "active": bool(raw.get("active", False)),
        "closed": is_closed,
        "status": "closed" if is_closed else ("active" if raw.get("active", False) else "inactive"),
        "archived": bool(raw.get("archived", False)),
        "enable_order_book": bool(raw.get("enableOrderBook", False)),
        "volume": raw.get("volume"),
        "liquidity": raw.get("liquidity"),
        "matched_tags": matched_tags,
        "order_books": order_books,
        "price_histories": price_histories,
    }


def fetch_polymarket_catalog() -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({"User-Agent": "agentverse-finance-research/1.0"})

    open_candidates: dict[str, tuple[dict[str, Any], list[str]]] = {}
    historical_weather_candidates: dict[str, tuple[dict[str, Any], list[str]]] = {}
    general_live_clob: dict[str, tuple[dict[str, Any], list[str]]] = {}

    search_configs = [
        # Open / active markets first
        {"endpoint": "/events", "params": {"active": "true", "closed": "false", "tag_slug": "weather", "limit": 100}},
        {"endpoint": "/events", "params": {"active": "true", "closed": "false", "tag_slug": "science", "limit": 100}},
        {"endpoint": "/events", "params": {"active": "true", "closed": "false", "tag_slug": "uk", "limit": 100}},
        {"endpoint": "/events", "params": {"active": "true", "closed": "false", "tag_slug": "london", "limit": 100}},
        {"endpoint": "/events", "params": {"active": "true", "closed": "false", "limit": 100, "offset": 0}},
        {"endpoint": "/events", "params": {"active": "true", "closed": "false", "limit": 100, "offset": 100}},
        {"endpoint": "/events", "params": {"active": "true", "closed": "false", "limit": 100, "offset": 200}},
        # Historical weather markets (including London temperature markets)
        {"endpoint": "/events", "params": {"tag_slug": "weather", "limit": 100, "offset": 0}},
        {"endpoint": "/events", "params": {"tag_slug": "weather", "limit": 100, "offset": 100}},
    ]

    for cfg in search_configs:
        url = f"{GAMMA_BASE}{cfg['endpoint']}"
        try:
            resp = session.get(url, params=cfg["params"], timeout=15)
            if resp.status_code != 200:
                continue
            items = resp.json()
            if not isinstance(items, list):
                continue
            for item in items:
                ev_markets = item.get("markets", []) if cfg["endpoint"] == "/events" else [item]
                for m in ev_markets:
                    if not isinstance(m, dict):
                        continue
                    mid = str(m.get("id", ""))
                    if not mid:
                        continue
                    ok, tags = is_weather_or_uk_relevant(m)
                    is_closed = bool(m.get("closed", False))
                    if ok:
                        if not is_closed:
                            open_candidates[mid] = (m, tags)
                        else:
                            historical_weather_candidates[mid] = (m, tags)
                    elif not is_closed and m.get("enableOrderBook") and len(general_live_clob) < 8:
                        general_live_clob[mid] = (m, ["general_active_clob_sample"])
        except requests.RequestException as exc:
            print(f"Warning: request to {url} failed: {exc}")

    selected: list[tuple[dict[str, Any], list[str]]] = []
    # 1. All open weather/UK markets (up to 15)
    for pair in list(open_candidates.values())[:15]:
        selected.append(pair)

    # 2. Diverse historical weather markets (London + NYC/Seoul/etc., up to 15)
    london_hist = [
        p for p in historical_weather_candidates.values()
        if any("london" in t for t in p[1])
    ]
    other_hist = [
        p for p in historical_weather_candidates.values()
        if not any("london" in t for t in p[1])
    ]
    selected.extend(london_hist[:10])
    selected.extend(other_hist[:6])

    # 3. Live CLOB benchmark markets with active order books
    selected.extend(list(general_live_clob.values())[:5])

    records: list[dict[str, Any]] = []
    for raw_m, tags in selected:
        rec = normalize_market_record(session, raw_m, tags, fetch_clob=True)
        records.append(rec)

    POLYMARKET_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = POLYMARKET_CACHE_DIR / "authentic_polymarket_snapshots.json"
    payload = {
        "schema_version": "1.1",
        "retrieved_at": utc_now_iso(),
        "source": "Polymarket Public Gamma & CLOB APIs (read-only)",
        "gamma_base_url": GAMMA_BASE,
        "clob_base_url": CLOB_BASE,
        "open_weather_or_uk_count": len(open_candidates),
        "historical_weather_or_uk_count": len(historical_weather_candidates),
        "market_count": len(records),
        "markets": records,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"Saved {len(records)} authentic Polymarket snapshots "
        f"(open_weather_uk={len(open_candidates)}, hist_weather_uk={len(historical_weather_candidates)}) "
        f"to {out_path}"
    )
    return payload


if __name__ == "__main__":
    fetch_polymarket_catalog()
    raw_csv = RAW_DATA_DIR / "london_weather_real_2022_2025.csv"
    if not raw_csv.exists():
        from scripts.fetch_external_data import fetch_london_historical_weather
