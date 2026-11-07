"""Feature preparation and validation for training and saved-model inference.

Guarantees identical feature names, types, and ordering between training and inference,
and enforces strict temporal causality (no lookahead or future leakage).
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin

from src.business_data import UK_BANK_HOLIDAYS_2022_2025


class WeekdayMeanBaseline(BaseEstimator, RegressorMixin):
    """Simple baseline predicting historical average daily revenue for the relevant weekday."""

    def __init__(self) -> None:
        self.weekday_means_: dict[int, float] = {}
        self.global_mean_: float = 0.0

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> "WeekdayMeanBaseline":
        y_series = pd.Series(np.asarray(y, dtype=float), index=X.index)
        dow = X["day_of_week"].astype(int)
        self.global_mean_ = float(y_series.mean())
        self.weekday_means_ = {
            int(k): float(v) for k, v in y_series.groupby(dow).mean().items()
        }
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        dow = X["day_of_week"].astype(int)
        preds = dow.map(self.weekday_means_).fillna(self.global_mean_)
        return preds.to_numpy(dtype=float)

CATEGORICAL_FEATURES = [
    "day_of_week",
    "month",
]

NUMERIC_FEATURES = [
    "temp_max_c",
    "temp_min_c",
    "temp_mean_c",
    "precipitation_mm",
    "rain_mm",
    "wind_max_kmh",
    "sunshine_hours",
    "opening_hours",
    "indoor_capacity",
    "outdoor_capacity",
    "is_weekend",
    "is_uk_bank_holiday",
    "local_event_indicator",
    "sin_day_of_year",
    "cos_day_of_year",
    "outdoor_seat_ratio",
    "warm_dry_outdoor_index",
    "rain_weekend_interaction",
    "is_rainy_day",
    "is_heavy_rain",
    "lag_7d_revenue_gbp",
    "rolling_14d_mean_revenue_gbp",
]

ALL_MODEL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET_COLUMN = "daily_revenue_gbp"


def build_feature_frame(
    raw_df: pd.DataFrame,
    weekday_fallback_means: dict[int, float] | None = None,
) -> pd.DataFrame:
    """Transform raw daily records into the exact model feature matrix X.

    All derived features use only same-day known calendar/capacity/weather inputs
    and strictly past revenue lags (t-7 and [t-14..t-1]).
    """
    df = raw_df.copy()
    if "date" not in df.columns:
        raise ValueError("Input DataFrame must contain a 'date' column (YYYY-MM-DD).")

    dt_series = pd.to_datetime(df["date"])
    df["day_of_week"] = dt_series.dt.dayofweek.astype(int)
    df["month"] = dt_series.dt.month.astype(int)
    day_of_year = dt_series.dt.dayofyear.astype(float)

    df["is_weekend"] = df["day_of_week"].isin([4, 5, 6]).astype(int)
    if "is_uk_bank_holiday" not in df.columns:
        df["is_uk_bank_holiday"] = df["date"].isin(UK_BANK_HOLIDAYS_2022_2025).astype(int)
    else:
        df["is_uk_bank_holiday"] = df["is_uk_bank_holiday"].fillna(0).astype(int)

    if "local_event_indicator" not in df.columns:
        df["local_event_indicator"] = 0
    else:
        df["local_event_indicator"] = df["local_event_indicator"].fillna(0).astype(int)

    if "indoor_capacity" not in df.columns:
        df["indoor_capacity"] = 90
    if "outdoor_capacity" not in df.columns:
        df["outdoor_capacity"] = 70
    if "opening_hours" not in df.columns:
        weekday_hours_map = {0: 10.0, 1: 10.0, 2: 10.5, 3: 11.0, 4: 12.5, 5: 12.5, 6: 10.5}
        df["opening_hours"] = df["day_of_week"].map(weekday_hours_map) + df["is_uk_bank_holiday"] * 1.0

    df["sin_day_of_year"] = np.sin(2.0 * np.pi * day_of_year / 365.25)
    df["cos_day_of_year"] = np.cos(2.0 * np.pi * day_of_year / 365.25)

    total_cap = np.maximum(1.0, df["indoor_capacity"].astype(float) + df["outdoor_capacity"].astype(float))
    df["outdoor_seat_ratio"] = df["outdoor_capacity"].astype(float) / total_cap

    temp_above_14 = np.maximum(0.0, df["temp_max_c"].astype(float) - 14.0)
    dry_factor = np.where(df["rain_mm"].astype(float) < 1.0, 1.0, np.exp(-0.25 * df["rain_mm"].astype(float)))
    df["warm_dry_outdoor_index"] = temp_above_14 * df["outdoor_capacity"].astype(float) * dry_factor

    df["rain_weekend_interaction"] = df["rain_mm"].astype(float) * df["is_weekend"].astype(float)
    df["is_rainy_day"] = (df["rain_mm"].astype(float) >= 2.0).astype(int)
    df["is_heavy_rain"] = (df["rain_mm"].astype(float) >= 8.0).astype(int)

    # Handle lagged revenue columns without any future leakage
    for lag_col in ["lag_7d_revenue_gbp", "rolling_14d_mean_revenue_gbp"]:
        if lag_col not in df.columns:
            df[lag_col] = np.nan
        if weekday_fallback_means is not None:
            fallback_series = df["day_of_week"].map(weekday_fallback_means)
            overall_mean = float(np.mean(list(weekday_fallback_means.values()))) if weekday_fallback_means else 2400.0
            df[lag_col] = df[lag_col].astype(float).fillna(fallback_series).fillna(overall_mean)

    return df[ALL_MODEL_FEATURES].copy()


def get_feature_schema() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "target_column": TARGET_COLUMN,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "all_model_features": ALL_MODEL_FEATURES,
        "feature_count": len(ALL_MODEL_FEATURES),
        "causality_rule": (
            "All features for date t depend only on calendar/operational settings for date t, "
            "forecast or observed weather for date t, and revenue strictly prior to date t "
            "(t-7 and [t-14, t-1])."
        ),
    }
