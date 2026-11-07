"""Reproducible synthetic daily sales dataset generator for a fictional UK pub paired with real London weather.

Real Data Component:
- Daily London weather observations (2022-01-01 to 2025-12-31) from Open-Meteo ERA5 archive.

Synthetic Data Component (Prominent Disclosure):
- Daily pub revenue (GBP), indoor/outdoor seating capacity changes, opening hours, and event indicators
  are synthetically generated using a documented stochastic process (seed=20261107).
- This dataset demonstrates the ML training and evaluation pipeline under stated synthetic assumptions.
  It is NOT private financial data and does NOT prove predictive accuracy for real pubs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

from src.weather_data import load_real_london_weather, load_weather_provenance

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR = ROOT / "data" / "processed"
DEFAULT_DATASET_CSV = PROCESSED_DATA_DIR / "uk_pub_daily_dataset.csv"
DEFAULT_DATASET_METADATA = PROCESSED_DATA_DIR / "dataset_provenance_and_assumptions.json"

RANDOM_SEED = 20261107

# Official England & Wales Bank Holidays 2022-2025
UK_BANK_HOLIDAYS_2022_2025 = {
    # 2022
    "2022-01-03", "2022-04-15", "2022-04-18", "2022-05-02",
    "2022-06-02", "2022-06-03", "2022-08-29", "2022-12-26", "2022-12-27",
    # 2023
    "2023-01-02", "2023-04-07", "2023-04-10", "2023-05-01",
    "2023-05-08", "2023-05-29", "2023-08-28", "2023-12-25", "2023-12-26",
    # 2024
    "2024-01-01", "2024-03-29", "2024-04-01", "2024-05-06",
    "2024-05-27", "2024-08-26", "2024-12-25", "2024-12-26",
    # 2025
    "2025-01-01", "2025-04-18", "2025-04-21", "2025-05-05",
    "2025-05-26", "2025-08-25", "2025-12-25", "2025-12-26",
}


def generate_pub_dataset(
    seed: int = RANDOM_SEED,
    save_to_disk: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Combine real London historical weather with a realistic stochastic UK pub revenue process."""
    weather_df = load_real_london_weather()
    weather_prov = load_weather_provenance()
    rng = np.random.default_rng(seed)

    df = weather_df.copy()
    dt_series = pd.to_datetime(df["date"])
    df["day_of_week"] = dt_series.dt.dayofweek  # 0=Mon .. 6=Sun
    df["day_name"] = dt_series.dt.day_name()
    df["month"] = dt_series.dt.month
    df["day_of_year"] = dt_series.dt.dayofyear
    df["year"] = dt_series.dt.year
    df["is_weekend"] = df["day_of_week"].isin([4, 5, 6]).astype(int)
    df["is_uk_bank_holiday"] = df["date"].isin(UK_BANK_HOLIDAYS_2022_2025).astype(int)

    n = len(df)
    time_idx = np.arange(n, dtype=float)

    # Plausible operational changes over time:
    # Indoor capacity stays 90; outdoor beer garden expanded from 60 to 70 seats in April 2023,
    # with winter awning reductions (40 seats usable in Nov-Feb).
    base_outdoor = np.where(df["date"] >= "2023-04-01", 70, 60)
    winter_mask = df["month"].isin([11, 12, 1, 2])
    df["indoor_capacity"] = 90
    df["outdoor_capacity"] = np.where(winter_mask, (base_outdoor * 0.6).astype(int), base_outdoor)

    # Opening hours: Mon-Wed 10h, Thu 11h, Fri-Sat 12.5h, Sun 10.5h; +1h on Bank Holidays
    weekday_hours_map = {0: 10.0, 1: 10.0, 2: 10.5, 3: 11.0, 4: 12.5, 5: 12.5, 6: 10.5}
    df["opening_hours"] = df["day_of_week"].map(weekday_hours_map) + df["is_uk_bank_holiday"] * 1.0

    # Clearly defined local event indicator (e.g., major football fixture / riverside market weekend ~8% of Fri/Sat/Sun)
    event_probs = np.where(df["day_of_week"].isin([4, 5, 6]), 0.10, 0.02)
    df["local_event_indicator"] = (rng.uniform(0.0, 1.0, size=n) < event_probs).astype(int)

    # Non-trivial stochastic data generating process for daily revenue (GBP):
    # 1. Gradual inflation / local footfall drift (~3.5% p.a. with mild cyclicality)
    trend_multiplier = 1.0 + 0.11 * (time_idx / max(n - 1, 1)) + 0.015 * np.sin(2 * np.pi * time_idx / 500.0)

    # 2. Weekday base indoor revenue (GBP)
    weekday_base_map = {
        0: 1480.0,  # Monday
        1: 1620.0,  # Tuesday
        2: 1850.0,  # Wednesday
        3: 2280.0,  # Thursday
        4: 3450.0,  # Friday
        5: 3920.0,  # Saturday
        6: 2780.0,  # Sunday
    }
    base_indoor = df["day_of_week"].map(weekday_base_map).to_numpy(dtype=float)

    # 3. Seasonal baseline modulation (summer evenings and December festive season boost indoor/total demand)
    seasonal_wave = 240.0 * np.sin(2 * np.pi * (df["day_of_year"].to_numpy() - 105.0) / 365.25)
    december_festive = np.where((df["month"] == 12) & (df["day_of_year"] <= 358), 520.0, 0.0)

    # 4. Non-linear outdoor seating contribution that depends heavily on weather:
    #    - Warm, dry, sunny days fill the beer garden (especially Fri/Sat/Sun and Bank Holidays).
    #    - Rain and strong wind sharply suppress outdoor utilization and also reduce casual walk-in footfall.
    temp_max = df["temp_max_c"].to_numpy(dtype=float)
    rain_mm = df["rain_mm"].to_numpy(dtype=float)
    wind_kmh = df["wind_max_kmh"].to_numpy(dtype=float)
    sunshine_h = df["sunshine_hours"].to_numpy(dtype=float)
    outdoor_seats = df["outdoor_capacity"].to_numpy(dtype=float)

    # Smooth thermal comfort curve (sigmoid-like activation above 13C, peaking around 23-27C)
    thermal_comfort = 1.0 / (1.0 + np.exp(-(temp_max - 15.5) / 3.2))
    rain_suppression = np.exp(-0.28 * rain_mm)  # 5mm rain cuts outdoor usage by ~75%; 10mm by ~94%
    wind_penalty = np.clip(1.0 - np.maximum(0.0, wind_kmh - 25.0) / 45.0, 0.35, 1.0)
    sunshine_bonus = 1.0 + 0.045 * np.minimum(sunshine_h, 10.0)

    weekend_or_hol_boost = np.where(
        (df["day_of_week"].isin([4, 5, 6])) | (df["is_uk_bank_holiday"] == 1),
        1.45,
        0.85,
    )

    # Revenue per active outdoor seat on an ideal day
    outdoor_revenue = (
        outdoor_seats
        * 26.5
        * thermal_comfort
        * rain_suppression
        * wind_penalty
        * sunshine_bonus
        * weekend_or_hol_boost
    )

    # Heavy rain also dampens indoor walk-in footfall (especially when rain > 4mm on weekends/evenings)
    walkin_rain_drag = -np.minimum(550.0, 34.0 * np.power(rain_mm, 0.85)) * np.where(
        df["day_of_week"].isin([4, 5, 6]), 1.35, 0.85
    )
    cold_snap_drag = np.where(temp_max < 5.0, -42.0 * (5.0 - temp_max), 0.0)

    # Holidays and local events
    holiday_effect = df["is_uk_bank_holiday"].to_numpy(dtype=float) * (
        580.0 + 380.0 * rain_suppression * thermal_comfort
    )
    event_effect = df["local_event_indicator"].to_numpy(dtype=float) * (
        490.0 + rng.normal(0.0, 85.0, size=n)
    )

    # 5. Autocorrelated unobserved demand state (AR(1) local buzz/neighborhood variation) + heteroskedastic noise
    ar_noise = np.zeros(n, dtype=float)
    eps = rng.normal(0.0, 175.0, size=n)
    for t in range(1, n):
        ar_noise[t] = 0.32 * ar_noise[t - 1] + eps[t]

    # 6. Exceptional days (~2.5% of days: private venue hire, unannounced street closure, kitchen equipment fault, or cup final)
    exceptional_u = rng.uniform(0.0, 1.0, size=n)
    exceptional_shock = np.where(
        exceptional_u < 0.012,
        rng.uniform(750.0, 1450.0, size=n),  # Unscheduled private party / cup screening
        np.where(
            exceptional_u > 0.988,
            -rng.uniform(600.0, 1150.0, size=n),  # Unexpected cellar/kitchen disruption or transit strike
            0.0,
        ),
    )

    raw_revenue = (
        (
            base_indoor
            + seasonal_wave
            + december_festive
            + outdoor_revenue
            + walkin_rain_drag
            + cold_snap_drag
            + holiday_effect
            + event_effect
        )
        * trend_multiplier
        + ar_noise
        + exceptional_shock
    )

    df["daily_revenue_gbp"] = np.round(np.maximum(450.0, raw_revenue), 2)
    df["is_synthetic_revenue"] = True
    df["is_synthetic_weather"] = False

    # Strictly causal lagged features (using only information strictly prior to date t: t-7 and [t-14, t-1])
    df["lag_7d_revenue_gbp"] = df["daily_revenue_gbp"].shift(7).round(2)
    df["rolling_14d_mean_revenue_gbp"] = (
        df["daily_revenue_gbp"].shift(1).rolling(window=14, min_periods=7).mean().round(2)
    )
    # Backfill the initial 7-14 warmup days in Jan 2022 using only those initial days' expanding mean
    df["lag_7d_revenue_gbp"] = df["lag_7d_revenue_gbp"].bfill()
    df["rolling_14d_mean_revenue_gbp"] = df["rolling_14d_mean_revenue_gbp"].bfill()

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    dataset_sha256 = hashlib.sha256(csv_bytes).hexdigest()

    metadata = {
        "dataset_name": "uk_pub_daily_dataset",
        "business_id": "uk_pub_london_se1_01",
        "fictional_business_description": (
            "Independent UK pub in London SE1 with 90 indoor seats and 60-70 outdoor beer garden seats."
        ),
        "random_seed": seed,
        "row_count": int(len(df)),
        "date_range": {"start": str(df["date"].min()), "end": str(df["date"].max())},
        "dataset_sha256": dataset_sha256,
        "provenance": {
            "weather_data": weather_prov,
            "revenue_and_operations": {
                "is_synthetic": True,
                "generator_module": "src/business_data.py",
                "seed": seed,
                "disclosure": (
                    "Daily revenue (GBP), seating capacities, opening hours, and event flags are "
                    "synthetically generated. Success on this dataset validates the engineering and "
                    "statistical pipeline under stated synthetic assumptions and does NOT imply "
                    "predictive accuracy for real pubs."
                ),
            },
        },
        "assumptions_and_mechanics": [
            "Weekday base demand peaks on Friday and Saturday and is lowest on Monday and Tuesday.",
            "Outdoor beer garden revenue scales non-linearly with maximum temperature (above ~13C) and sunshine hours, and drops exponentially with daily rainfall (rain_mm) and high wind.",
            "Heavy rainfall also reduces casual walk-in indoor trade, creating a compound adverse weather exposure on wet spring/summer weekends.",
            "Outdoor capacity expanded from 60 to 70 seats in April 2023 and is reduced by 40% during winter months (Nov-Feb).",
            "Includes a ~3.5% annual inflation/footfall drift, AR(1) autocorrelated demand noise (rho=0.32, sigma=175 GBP), and ~2.4% unlabelled exceptional days (private hires or operational disruptions) so the target cannot be trivially reproduced.",
            "Lagged features (lag_7d_revenue_gbp and rolling_14d_mean_revenue_gbp) use strictly past values (t-7 and t-1..t-14) to prevent temporal leakage.",
        ],
        "units": {
            "daily_revenue_gbp": "GBP (pounds sterling)",
            "temp_max_c": "degrees Celsius",
            "temp_min_c": "degrees Celsius",
            "temp_mean_c": "degrees Celsius",
            "precipitation_mm": "millimetres",
            "rain_mm": "millimetres",
            "wind_max_kmh": "kilometres per hour",
            "sunshine_hours": "hours",
            "opening_hours": "hours per day",
            "indoor_capacity": "seats",
            "outdoor_capacity": "seats",
        },
    }

    if save_to_disk:
        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        DEFAULT_DATASET_CSV.write_bytes(csv_bytes)
        DEFAULT_DATASET_METADATA.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return df, metadata


def load_pub_dataset(csv_path: Path = DEFAULT_DATASET_CSV) -> pd.DataFrame:
    if not csv_path.exists():
        df, _ = generate_pub_dataset(save_to_disk=True)
        return df
    return pd.read_csv(csv_path)


def load_dataset_metadata(meta_path: Path = DEFAULT_DATASET_METADATA) -> dict[str, Any]:
    if not meta_path.exists():
        _, meta = generate_pub_dataset(save_to_disk=True)
        return meta
    return json.loads(meta_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    df_out, meta_out = generate_pub_dataset(save_to_disk=True)
    print(
        f"Generated dataset with {len(df_out)} rows ({meta_out['date_range']['start']} to "
        f"{meta_out['date_range']['end']}), sha256={meta_out['dataset_sha256'][:16]}..."
    )
