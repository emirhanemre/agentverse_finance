"""Open-Meteo: ERA5-based archive (what happened) and historical forecast archive
(what was forecast at the time). CC BY 4.0, attribution "Weather data by Open-Meteo.com"."""
import httpx

from .. import cache

LICENCE = "CC BY 4.0 · Weather data by Open-Meteo.com (https://open-meteo.com/en/license)"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
HISTFC = "https://historical-forecast-api.open-meteo.com/v1/forecast"
FORECAST = "https://api.open-meteo.com/v1/forecast"

DAILY = "precipitation_sum,temperature_2m_max,precipitation_hours,sunshine_duration"


def _get(url: str, params: dict) -> dict:
    r = httpx.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def daily(lat: float, lon: float, start: str, end: str, kind: str = "archive") -> dict:
    """kind='archive' (observed reanalysis) or 'forecast' (archived past forecasts).
    Includes hourly precipitation so we can isolate 12:00-18:00."""
    url = ARCHIVE if kind == "archive" else HISTFC
    params = {"latitude": round(lat, 4), "longitude": round(lon, 4), "start_date": start, "end_date": end,
              "daily": DAILY, "hourly": "precipitation", "timezone": "Europe/London"}
    key = f"{kind}:{params['latitude']}:{params['longitude']}:{start}:{end}"
    return cache.fetch("openmeteo", key, lambda: _get(url, params), source=f"Open-Meteo {kind}",
                       url=url, licence=LICENCE, max_age_s=30 * 86400, record=False)


def afternoon_rain(env: dict) -> dict:
    """Map date -> mm of rain between 12:00 and 18:00 local."""
    h = env["data"]["hourly"]
    out: dict = {}
    for t, mm in zip(h["time"], h["precipitation"]):
        if 12 <= int(t[11:13]) < 18:
            out[t[:10]] = round(out.get(t[:10], 0.0) + (mm or 0.0), 2)
    return out
