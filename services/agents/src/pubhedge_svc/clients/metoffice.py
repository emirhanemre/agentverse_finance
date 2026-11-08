"""Met Office Weather DataHub, Site Specific forecast (global spot data).
Free tier ~360 calls/day: cached by location and model run, max one live call per hour."""
import os

import httpx

from .. import cache

BASE = "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point"
LICENCE = "Met Office Weather DataHub terms · © Crown copyright, Met Office"


def _get(kind: str, lat: float, lon: float) -> dict:
    r = httpx.get(f"{BASE}/{kind}", params={"latitude": lat, "longitude": lon, "includeLocationName": "true"},
                  headers={"apikey": os.environ["METOFFICE_DATAHUB_KEY"], "accept": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()


def forecast(lat: float, lon: float, kind: str = "hourly") -> dict:
    lat, lon = round(lat, 3), round(lon, 3)
    key = f"{kind}:{lat}:{lon}"
    env = cache.fetch("metoffice", key, lambda: _get(kind, lat, lon), source=f"Met Office DataHub {kind}",
                      url=f"{BASE}/{kind}", licence=LICENCE, max_age_s=3600, record=False)
    props = env["data"]["features"][0]["properties"]
    env["grid_point"] = {"name": props.get("location", {}).get("name"),
                         "distance_m": round(props.get("requestPointDistance", 0)),
                         "model_run": props.get("modelRunDate")}
    return env


def afternoon_rain(env: dict) -> dict:
    """date -> (mm 12:00-18:00 UTC-ish local, max probability of precipitation %)."""
    out: dict = {}
    for row in env["data"]["features"][0]["properties"]["timeSeries"]:
        t = row["time"]
        if 12 <= int(t[11:13]) < 18:
            d = out.setdefault(t[:10], {"mm": 0.0, "prob_max": 0})
            d["mm"] = round(d["mm"] + (row.get("totalPrecipAmount") or 0.0), 2)
            d["prob_max"] = max(d["prob_max"], row.get("probOfPrecipitation") or 0)
    return out
