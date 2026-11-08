"""Build compact daily weather tables from Open-Meteo (CC BY 4.0).

Writes data/weather/<loc>.csv: observed (ERA5 archive) and what was forecast at the
time (historical forecast archive), including 12:00-18:00 rain. Run via:
  uv run --project services/agents python scripts/build_weather.py
"""
import csv
import json
from pathlib import Path

from pubhedge_svc.clients import openmeteo as om

ROOT = Path(__file__).resolve().parents[1]
LOCS = {"N4": (51.5687, -0.1086), "SE22": (51.4563, -0.0759), "E2": (51.5313, -0.0556), "W12": (51.5072, -0.2248)}
START, END = "2021-01-01", "2026-10-31"


def r(v, n=2):
    return "" if v is None else round(v, n)


def main():
    out = ROOT / "data" / "weather"
    out.mkdir(parents=True, exist_ok=True)
    meta = {"source": "Open-Meteo archive (ERA5) and historical forecast API", "licence": om.LICENCE,
            "start": START, "end": END, "locations": {}}
    for name, (lat, lon) in LOCS.items():
        obs, fc = om.daily(lat, lon, START, END, "archive"), om.daily(lat, lon, START, END, "forecast")
        pm_o, pm_f = om.afternoon_rain(obs), om.afternoon_rain(fc)
        d_o, d_f = obs["data"]["daily"], fc["data"]["daily"]
        with open(out / f"{name}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "rain_mm", "pm_rain_mm", "tmax_c", "sun_h", "fc_rain_mm", "fc_pm_rain_mm", "fc_tmax_c"])
            for i, day in enumerate(d_o["time"]):
                w.writerow([day, r(d_o["precipitation_sum"][i]), pm_o.get(day, ""), r(d_o["temperature_2m_max"][i], 1),
                            r((d_o["sunshine_duration"][i] or 0) / 3600, 1), r(d_f["precipitation_sum"][i]),
                            pm_f.get(day, ""), r(d_f["temperature_2m_max"][i], 1)])
        meta["locations"][name] = {"lat": lat, "lon": lon, "grid_lat": obs["data"]["latitude"],
                                   "grid_lon": obs["data"]["longitude"], "fetched_at": obs["fetched_at"]}
    (out / "manifest.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
