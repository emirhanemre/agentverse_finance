"""Real historical weather data loader, validator, reference scenario builder, and training-range checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WEATHER_CSV = ROOT / "data" / "raw" / "london_weather_real_2022_2025.csv"
DEFAULT_WEATHER_PROVENANCE = ROOT / "data" / "raw" / "london_weather_provenance.json"

REQUIRED_WEATHER_COLS = [
    "date",
    "temp_max_c",
    "temp_min_c",
    "temp_mean_c",
    "precipitation_mm",
    "rain_mm",
    "wind_max_kmh",
    "sunshine_hours",
]


def load_real_london_weather(csv_path: Path = DEFAULT_WEATHER_CSV) -> pd.DataFrame:
    """Load real daily London weather observations from Open-Meteo ERA5 archive."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Weather file not found at {csv_path}")
    df = pd.read_csv(csv_path)
    missing = [c for c in REQUIRED_WEATHER_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Weather dataset missing required columns: {missing}")
    df = df.sort_values("date").reset_index(drop=True)
    return df


def load_weather_provenance(prov_path: Path = DEFAULT_WEATHER_PROVENANCE) -> dict[str, Any]:
    if not prov_path.exists():
        return {"source_name": "Unknown", "is_synthetic": False}
    return json.loads(prov_path.read_text(encoding="utf-8"))


def compute_monthly_reference_weather(weather_df: pd.DataFrame, max_train_date: str = "2024-05-26") -> dict[int, dict[str, float]]:
    """Compute typical benign/dry seasonal reference weather by calendar month using training data only."""
    train_sub = weather_df[weather_df["date"] <= max_train_date].copy()
    if train_sub.empty:
        train_sub = weather_df.copy()
    train_sub["month"] = pd.to_datetime(train_sub["date"]).dt.month

    monthly_ref: dict[int, dict[str, float]] = {}
    for month, grp in train_sub.groupby("month"):
        # Reference scenario: dry seasonal day (rain=0mm, median dry-day sunshine and temperature)
        dry_grp = grp[grp["rain_mm"] < 1.0]
        source_grp = dry_grp if len(dry_grp) >= 5 else grp
        monthly_ref[int(month)] = {
            "temp_max_c": round(float(source_grp["temp_max_c"].median()), 1),
            "temp_min_c": round(float(source_grp["temp_min_c"].median()), 1),
            "temp_mean_c": round(float(source_grp["temp_mean_c"].median()), 1),
            "precipitation_mm": 0.0,
            "rain_mm": 0.0,
            "wind_max_kmh": round(float(source_grp["wind_max_kmh"].median()), 1),
            "sunshine_hours": round(float(source_grp["sunshine_hours"].median()), 1),
        }
    return monthly_ref


def compute_training_weather_bounds(weather_df: pd.DataFrame, max_train_date: str = "2024-05-26") -> dict[str, dict[str, float]]:
    """Compute observed min/max/quantiles on the training split to detect out-of-range scenario inputs."""
    train_sub = weather_df[weather_df["date"] <= max_train_date].copy()
    bounds: dict[str, dict[str, float]] = {}
    for col in [
        "temp_max_c",
        "temp_min_c",
        "temp_mean_c",
        "precipitation_mm",
        "rain_mm",
        "wind_max_kmh",
        "sunshine_hours",
    ]:
        series = train_sub[col].dropna()
        bounds[col] = {
            "min": round(float(series.min()), 2),
            "p01": round(float(series.quantile(0.01)), 2),
            "p99": round(float(series.quantile(0.99)), 2),
            "max": round(float(series.max()), 2),
        }
    return bounds


def check_weather_out_of_range(
    inputs: dict[str, Any],
    training_bounds: dict[str, dict[str, float]],
) -> list[str]:
    """Return human-readable reasons if any weather input falls outside the observed training range."""
    reasons: list[str] = []
    for col, b in training_bounds.items():
        if col not in inputs or inputs[col] is None:
            continue
        val = float(inputs[col])
        if val < b["min"] or val > b["max"]:
            reasons.append(
                f"{col}={val:.1f} is outside the training data range [{b['min']:.1f}, {b['max']:.1f}]"
            )
    return reasons
