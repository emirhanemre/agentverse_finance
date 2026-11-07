"""Saved-model inference and weather scenario exposure estimation.

Loads the frozen fitted model artifact from disk without retraining on page refresh.
Compares predicted revenue under selected/forecast weather against an explicitly
defined seasonal reference weather scenario.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
import joblib
import pandas as pd

from src.business_data import UK_BANK_HOLIDAYS_2022_2025, load_pub_dataset
from src.features import build_feature_frame
from src.schemas import (
    DailyFeatureInput,
    RevenuePredictionOutput,
    ScenarioComparisonOutput,
)
from src.training import FITTED_PIPELINE_PATH
from src.weather_data import check_weather_out_of_range


@lru_cache(maxsize=2)
def load_saved_model_bundle(bundle_path: str = str(FITTED_PIPELINE_PATH)) -> dict[str, Any]:
    path = Path(bundle_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Saved model bundle not found at {path}. Run `python3 -m src.training` first."
        )
    bundle = joblib.load(path)
    required_keys = {
        "model_version",
        "selected_model_name",
        "selected_pipeline",
        "all_fitted_models",
        "train_weekday_means",
        "training_weather_bounds",
        "monthly_reference_weather",
        "prediction_interval_80",
        "feature_schema",
    }
    missing = required_keys - set(bundle.keys())
    if missing:
        raise ValueError(f"Saved model bundle is missing required keys: {missing}")
    return bundle


def lookup_historical_lags_for_date(target_date: str) -> tuple[float | None, float | None]:
    """Look up strictly prior lagged revenue (t-7 and [t-14..t-1]) if available in historical dataset."""
    try:
        df = load_pub_dataset()
        row = df[df["date"] == target_date]
        if not row.empty:
            r = row.iloc[0]
            return float(r["lag_7d_revenue_gbp"]), float(r["rolling_14d_mean_revenue_gbp"])
    except Exception:
        pass
    return None, None


def predict_daily_revenue(
    feature_input: DailyFeatureInput,
    prediction_mode: Literal[
        "conditional_on_weather_scenario", "retrospective_observed_weather"
    ] = "conditional_on_weather_scenario",
    bundle_path: Path = FITTED_PIPELINE_PATH,
) -> RevenuePredictionOutput:
    """Predict daily GBP revenue using the frozen saved pipeline."""
    bundle = load_saved_model_bundle(str(bundle_path))
    selected_name = bundle["selected_model_name"]
    selected_pipe = bundle["selected_pipeline"]
    baseline_model = bundle["all_fitted_models"]["weekday_mean_baseline"]
    train_weekday_means = bundle["train_weekday_means"]
    weather_bounds = bundle["training_weather_bounds"]
    pi = bundle["prediction_interval_80"]

    payload = feature_input.model_dump()
    if payload.get("lag_7d_revenue_gbp") is None or payload.get("rolling_14d_mean_revenue_gbp") is None:
        hist_lag7, hist_roll14 = lookup_historical_lags_for_date(feature_input.date)
        if payload.get("lag_7d_revenue_gbp") is None and hist_lag7 is not None:
            payload["lag_7d_revenue_gbp"] = hist_lag7
        if payload.get("rolling_14d_mean_revenue_gbp") is None and hist_roll14 is not None:
            payload["rolling_14d_mean_revenue_gbp"] = hist_roll14

    raw_df = pd.DataFrame([payload])
    X = build_feature_frame(raw_df, weekday_fallback_means=train_weekday_means)

    pred_gbp = float(selected_pipe.predict(X)[0])
    base_gbp = float(baseline_model.predict(X)[0])

    low_gbp = max(0.0, pred_gbp + float(pi["residual_q_low_gbp"]))
    high_gbp = max(low_gbp, pred_gbp + float(pi["residual_q_high_gbp"]))

    oor_reasons = check_weather_out_of_range(payload, weather_bounds)

    return RevenuePredictionOutput(
        date=feature_input.date,
        predictor_used=selected_name,
        model_version=str(bundle["model_version"]),
        predicted_revenue_gbp=round(pred_gbp, 2),
        predicted_revenue_pence=int(round(pred_gbp * 100)),
        baseline_weekday_revenue_gbp=round(base_gbp, 2),
        prediction_interval_80_low_gbp=round(low_gbp, 2),
        prediction_interval_80_high_gbp=round(high_gbp, 2),
        interval_method=str(pi["method"]),
        is_out_of_training_range=len(oor_reasons) > 0,
        out_of_range_reasons=oor_reasons,
        prediction_mode=prediction_mode,
        synthetic_data_warning=(
            "Model trained on real London weather paired with synthetic pub revenue (seed=20261107). "
            "Predictions represent conditional scenario estimates under synthetic business assumptions."
        ),
    )


def get_reference_weather_for_date(
    target_date: str,
    bundle_path: Path = FITTED_PIPELINE_PATH,
) -> dict[str, float]:
    """Return the training-derived seasonal dry reference weather for the calendar month of target_date."""
    bundle = load_saved_model_bundle(str(bundle_path))
    month = int(pd.to_datetime(target_date).month)
    monthly_ref = bundle["monthly_reference_weather"]
    ref = monthly_ref.get(month) or monthly_ref.get(str(month))
    if not ref:
        return {
            "temp_max_c": 17.0,
            "temp_min_c": 10.0,
            "temp_mean_c": 13.5,
            "precipitation_mm": 0.0,
            "rain_mm": 0.0,
            "wind_max_kmh": 18.0,
            "sunshine_hours": 6.0,
        }
    return dict(ref)


def compare_weather_scenarios_for_date(
    target_date: str,
    adverse_weather: dict[str, float],
    reference_weather: dict[str, float] | None = None,
    indoor_capacity: int = 90,
    outdoor_capacity: int = 70,
    opening_hours: float | None = None,
    is_uk_bank_holiday: int | None = None,
    local_event_indicator: int = 0,
    scenario_label: str = "Forecast / Selected Adverse Weather",
    reference_label: str = "Seasonal Dry Reference Weather (Training Median Dry Day)",
    bundle_path: Path = FITTED_PIPELINE_PATH,
) -> ScenarioComparisonOutput:
    """Compare predicted pub revenue under an adverse weather scenario vs a defined reference weather scenario."""
    dt_val = pd.to_datetime(target_date)
    dow = int(dt_val.dayofweek)
    hol = (
        int(target_date in UK_BANK_HOLIDAYS_2022_2025)
        if is_uk_bank_holiday is None
        else int(is_uk_bank_holiday)
    )
    if opening_hours is None:
        weekday_hours_map = {0: 10.0, 1: 10.0, 2: 10.5, 3: 11.0, 4: 12.5, 5: 12.5, 6: 10.5}
        opening_hours = float(weekday_hours_map[dow] + hol * 1.0)

    if reference_weather is None:
        reference_weather = get_reference_weather_for_date(target_date, bundle_path=bundle_path)

    hist_lag7, hist_roll14 = lookup_historical_lags_for_date(target_date)

    adverse_input = DailyFeatureInput(
        date=target_date,
        temp_max_c=float(adverse_weather.get("temp_max_c", 14.0)),
        temp_min_c=float(adverse_weather.get("temp_min_c", adverse_weather.get("temp_max_c", 14.0) - 6.0)),
        temp_mean_c=float(adverse_weather.get("temp_mean_c", adverse_weather.get("temp_max_c", 14.0) - 3.0)),
        precipitation_mm=float(adverse_weather.get("precipitation_mm", adverse_weather.get("rain_mm", 0.0))),
        rain_mm=float(adverse_weather.get("rain_mm", 0.0)),
        wind_max_kmh=float(adverse_weather.get("wind_max_kmh", 22.0)),
        sunshine_hours=float(adverse_weather.get("sunshine_hours", 1.5)),
        opening_hours=opening_hours,
        indoor_capacity=indoor_capacity,
        outdoor_capacity=outdoor_capacity,
        is_uk_bank_holiday=hol,
        local_event_indicator=local_event_indicator,
        lag_7d_revenue_gbp=hist_lag7,
        rolling_14d_mean_revenue_gbp=hist_roll14,
    )

    reference_input = DailyFeatureInput(
        date=target_date,
        temp_max_c=float(reference_weather["temp_max_c"]),
        temp_min_c=float(reference_weather["temp_min_c"]),
        temp_mean_c=float(reference_weather["temp_mean_c"]),
        precipitation_mm=float(reference_weather["precipitation_mm"]),
        rain_mm=float(reference_weather["rain_mm"]),
        wind_max_kmh=float(reference_weather["wind_max_kmh"]),
        sunshine_hours=float(reference_weather["sunshine_hours"]),
        opening_hours=opening_hours,
        indoor_capacity=indoor_capacity,
        outdoor_capacity=outdoor_capacity,
        is_uk_bank_holiday=hol,
        local_event_indicator=local_event_indicator,
        lag_7d_revenue_gbp=hist_lag7,
        rolling_14d_mean_revenue_gbp=hist_roll14,
    )

    scen_pred = predict_daily_revenue(adverse_input, bundle_path=bundle_path)
    ref_pred = predict_daily_revenue(reference_input, bundle_path=bundle_path)

    diff_gbp = round(scen_pred.predicted_revenue_gbp - ref_pred.predicted_revenue_gbp, 2)
    downside_loss_gbp = round(max(0.0, ref_pred.predicted_revenue_gbp - scen_pred.predicted_revenue_gbp), 2)
    downside_loss_pence = int(round(downside_loss_gbp * 100))

    assumptions = [
        f"Calendar date {target_date} ({dt_val.day_name()}) with indoor={indoor_capacity} and outdoor={outdoor_capacity} seats held fixed across both scenarios.",
        f"Reference scenario uses training-split dry seasonal median for month {dt_val.month}: max temp {reference_input.temp_max_c:.1f}°C, rain {reference_input.rain_mm:.1f}mm, sunshine {reference_input.sunshine_hours:.1f}h.",
        f"Adverse scenario evaluates max temp {adverse_input.temp_max_c:.1f}°C, rain {adverse_input.rain_mm:.1f}mm, wind {adverse_input.wind_max_kmh:.1f}km/h, sunshine {adverse_input.sunshine_hours:.1f}h.",
        "Difference is a conditional model-based scenario estimate from the trained regression pipeline, not a guaranteed causal counterfactual.",
        "Weather sensitivity comes strictly from the business revenue model; Polymarket contract prices do not estimate pub revenue sensitivity.",
    ]
    if scen_pred.is_out_of_training_range:
        assumptions.append(
            "WARNING: One or more adverse weather inputs fall outside the training data range; tree-based predictions extrapolate flatly at boundary leaves."
        )

    return ScenarioComparisonOutput(
        date=target_date,
        scenario_label=scenario_label,
        reference_label=reference_label,
        scenario_predicted_revenue_gbp=scen_pred.predicted_revenue_gbp,
        reference_predicted_revenue_gbp=ref_pred.predicted_revenue_gbp,
        estimated_difference_gbp=diff_gbp,
        estimated_downside_loss_gbp=downside_loss_gbp,
        estimated_downside_loss_pence=downside_loss_pence,
        scenario_prediction=scen_pred,
        reference_prediction=ref_pred,
        assumptions=assumptions,
    )
