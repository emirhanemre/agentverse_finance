"""Honest regression evaluation metrics, subset error breakdowns, residual intervals, and markdown reporting.

Never uses undefined 'accuracy percentages' for continuous GBP revenue regression.
Reports MAE (GBP), RMSE (GBP), baseline comparison, subset errors with sample sizes,
and worst prediction errors on the untouched test split.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, root_mean_squared_error


def compute_regression_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    baseline_pred: np.ndarray | None = None,
) -> dict[str, Any]:
    """Compute MAE (GBP), RMSE (GBP), and comparison against the weekday baseline."""
    y_true_arr = np.asarray(y_true, dtype=float)
    y_pred_arr = np.asarray(y_pred, dtype=float)

    mae = float(mean_absolute_error(y_true_arr, y_pred_arr))
    rmse = float(root_mean_squared_error(y_true_arr, y_pred_arr))
    residuals = y_true_arr - y_pred_arr
    bias = float(np.mean(residuals))
    median_ae = float(np.median(np.abs(residuals)))

    out: dict[str, Any] = {
        "n_observations": int(len(y_true_arr)),
        "mae_gbp": round(mae, 2),
        "rmse_gbp": round(rmse, 2),
        "median_abs_error_gbp": round(median_ae, 2),
        "mean_signed_bias_gbp": round(bias, 2),
    }

    if baseline_pred is not None:
        base_arr = np.asarray(baseline_pred, dtype=float)
        base_mae = float(mean_absolute_error(y_true_arr, base_arr))
        base_rmse = float(root_mean_squared_error(y_true_arr, base_arr))
        mae_diff = base_mae - mae  # positive means improvement over baseline
        rmse_diff = base_rmse - rmse
        out["baseline_mae_gbp"] = round(base_mae, 2)
        out["baseline_rmse_gbp"] = round(base_rmse, 2)
        out["mae_improvement_vs_baseline_gbp"] = round(mae_diff, 2)
        out["mae_improvement_vs_baseline_pct"] = (
            round(100.0 * mae_diff / base_mae, 2) if base_mae > 0 else 0.0
        )
        out["rmse_improvement_vs_baseline_gbp"] = round(rmse_diff, 2)
        out["rmse_improvement_vs_baseline_pct"] = (
            round(100.0 * rmse_diff / base_rmse, 2) if base_rmse > 0 else 0.0
        )
        out["beats_baseline_on_mae"] = bool(mae < base_mae)
        out["beats_baseline_on_rmse"] = bool(rmse < base_rmse)

    return out


def compute_subset_evaluations(
    eval_df: pd.DataFrame,
    y_true_col: str,
    y_pred_col: str,
    baseline_col: str,
) -> dict[str, dict[str, Any]]:
    """Compute MAE, RMSE, baseline comparison, and sample size (n) on key weather and calendar subsets."""
    subsets = {
        "all_days": eval_df.index >= 0,
        "rainy_days_rain_ge_2mm": eval_df["rain_mm"] >= 2.0,
        "heavy_rain_days_rain_ge_8mm": eval_df["rain_mm"] >= 8.0,
        "dry_warm_days_temp_ge_18c_rain_lt_1mm": (eval_df["temp_max_c"] >= 18.0) & (eval_df["rain_mm"] < 1.0),
        "weekends_fri_sat_sun": eval_df["day_of_week"].isin([4, 5, 6]),
        "weekdays_mon_to_thu": eval_df["day_of_week"].isin([0, 1, 2, 3]),
        "uk_bank_holidays": eval_df["is_uk_bank_holiday"] == 1,
    }

    results: dict[str, dict[str, Any]] = {}
    for name, mask in subsets.items():
        sub = eval_df[mask]
        if len(sub) == 0:
            results[name] = {"n_observations": 0, "note": "No observations in subset"}
            continue
        results[name] = compute_regression_metrics(
            sub[y_true_col].to_numpy(),
            sub[y_pred_col].to_numpy(),
            sub[baseline_col].to_numpy(),
        )
    return results


def calibrate_empirical_prediction_interval(
    val_y_true: np.ndarray,
    val_y_pred: np.ndarray,
    alpha: float = 0.20,
) -> dict[str, Any]:
    """Calibrate an empirical residual quantile interval on validation data (e.g. 80% interval for alpha=0.20)."""
    residuals = np.asarray(val_y_true, dtype=float) - np.asarray(val_y_pred, dtype=float)
    q_low = float(np.quantile(residuals, alpha / 2.0))
    q_high = float(np.quantile(residuals, 1.0 - alpha / 2.0))
    return {
        "nominal_coverage": round(1.0 - alpha, 2),
        "alpha": alpha,
        "residual_q_low_gbp": round(q_low, 2),
        "residual_q_high_gbp": round(q_high, 2),
        "half_width_approx_gbp": round((q_high - q_low) / 2.0, 2),
        "method": (
            "Split-conformal / empirical residual quantiles (10th and 90th percentiles of "
            "validation-set residuals y_true - y_hat) added to point predictions."
        ),
        "limitations": (
            "Assumes exchangeability of residual distribution between validation and target periods; "
            "interval width is homoskedastic and may under-cover extreme unlabelled one-off events "
            "(such as unannounced street closures or private venue buyouts) or out-of-range weather."
        ),
    }


def evaluate_interval_coverage(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    q_low: float,
    q_high: float,
) -> float:
    y_true_arr = np.asarray(y_true, dtype=float)
    y_pred_arr = np.asarray(y_pred, dtype=float)
    lower = y_pred_arr + q_low
    upper = y_pred_arr + q_high
    covered = (y_true_arr >= lower) & (y_true_arr <= upper)
    return round(float(np.mean(covered)), 4)
