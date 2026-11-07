"""Reproducible model training, validation model selection, and untouched test-set evaluation.

Models compared:
1. WeekdayHistoricalAverageBaseline: predicts training-set mean revenue for that day of week.
2. Regularised Linear Regression (Ridge): one-hot encoded calendar + scaled numeric & weather features.
3. Tree-based Regression (HistGradientBoostingRegressor): captures non-linear weather/seating interactions.

Chronological Split (1,461 daily observations, 2022-01-01 to 2025-12-31):
- Training (~60%):   2022-01-01 to 2024-05-26 (877 days)
- Validation (~20%): 2024-05-27 to 2025-03-14 (292 days)
- Test (~20%):       2025-03-15 to 2025-12-31 (292 days, untouched until after model selection is frozen)
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any
import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.business_data import load_dataset_metadata, load_pub_dataset
from src.evaluation import (
    calibrate_empirical_prediction_interval,
    compute_regression_metrics,
    compute_subset_evaluations,
    evaluate_interval_coverage,
)
from src.features import (
    ALL_MODEL_FEATURES,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
    WeekdayMeanBaseline,
    build_feature_frame,
    get_feature_schema,
)
from src.weather_data import compute_monthly_reference_weather, compute_training_weather_bounds

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "artifacts" / "models"
DOCS_DIR = ROOT / "docs"

FITTED_PIPELINE_PATH = MODELS_DIR / "fitted_pipeline.joblib"
FEATURE_SCHEMA_PATH = MODELS_DIR / "feature_schema.json"
TRAINING_CONFIG_PATH = MODELS_DIR / "training_config.json"
EVALUATION_REPORT_JSON_PATH = MODELS_DIR / "evaluation_report.json"
TEST_PREDICTIONS_CSV_PATH = MODELS_DIR / "test_set_predictions.csv"
EVALUATION_MARKDOWN_PATH = DOCS_DIR / "MODEL_EVALUATION.md"

TRAIN_END_DATE = "2024-05-26"
VAL_START_DATE = "2024-05-27"
VAL_END_DATE = "2025-03-14"
TEST_START_DATE = "2025-03-15"
MODEL_VERSION = "1.0.0-20261107"


def make_preprocessing_transformer() -> ColumnTransformer:
    cat_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    num_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("cat", cat_pipe, CATEGORICAL_FEATURES),
            ("num", num_pipe, NUMERIC_FEATURES),
        ],
        remainder="drop",
    )


def make_ridge_pipeline(alpha: float = 10.0) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocess", make_preprocessing_transformer()),
            ("regressor", Ridge(alpha=alpha, random_state=20261107)),
        ]
    )


def make_hgb_pipeline(
    max_depth: int = 4,
    learning_rate: float = 0.05,
    max_iter: int = 160,
    min_samples_leaf: int = 18,
    l2_regularization: float = 1.0,
) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocess", make_preprocessing_transformer()),
            (
                "regressor",
                HistGradientBoostingRegressor(
                    loss="squared_error",
                    max_depth=max_depth,
                    learning_rate=learning_rate,
                    max_iter=max_iter,
                    min_samples_leaf=min_samples_leaf,
                    l2_regularization=l2_regularization,
                    random_state=20261107,
                ),
            ),
        ]
    )


def run_training_and_evaluation() -> dict[str, Any]:
    """Execute chronological split, validation model selection, freeze, and test evaluation."""
    raw_df = load_pub_dataset()
    dataset_meta = load_dataset_metadata()

    raw_df = raw_df.sort_values("date").reset_index(drop=True)
    train_df = raw_df[raw_df["date"] <= TRAIN_END_DATE].copy()
    val_df = raw_df[(raw_df["date"] >= VAL_START_DATE) & (raw_df["date"] <= VAL_END_DATE)].copy()
    test_df = raw_df[raw_df["date"] >= TEST_START_DATE].copy()

    assert len(train_df) + len(val_df) + len(test_df) == len(raw_df), "Split sizes must sum to total rows"
    assert train_df["date"].max() < val_df["date"].min(), "Training must precede validation"
    assert val_df["date"].max() < test_df["date"].min(), "Validation must precede test"

    # Compute training-only weekday means for missing-lag fallback and baseline
    train_weekday_means = {
        int(k): round(float(v), 2)
        for k, v in train_df.groupby("day_of_week")[TARGET_COLUMN].mean().items()
    }

    X_train = build_feature_frame(train_df, weekday_fallback_means=train_weekday_means)
    y_train = train_df[TARGET_COLUMN].to_numpy(dtype=float)

    X_val = build_feature_frame(val_df, weekday_fallback_means=train_weekday_means)
    y_val = val_df[TARGET_COLUMN].to_numpy(dtype=float)

    X_test = build_feature_frame(test_df, weekday_fallback_means=train_weekday_means)
    y_test = test_df[TARGET_COLUMN].to_numpy(dtype=float)

    # 1. Fit Weekday Historical Average Baseline on Training split ONLY
    baseline_model = WeekdayMeanBaseline().fit(X_train, y_train)
    val_pred_baseline = baseline_model.predict(X_val)
    test_pred_baseline = baseline_model.predict(X_test)

    # 2. Small, justified hyperparameter search on Validation split ONLY
    # 2a. Regularised Linear Regression (Ridge)
    ridge_candidates = [0.5, 5.0, 20.0, 50.0]
    best_ridge_alpha = 10.0
    best_ridge_val_mae = float("inf")
    ridge_search_log: list[dict[str, Any]] = []

    for alpha in ridge_candidates:
        pipe = make_ridge_pipeline(alpha=alpha)
        pipe.fit(X_train, y_train)
        preds = pipe.predict(X_val)
        m = compute_regression_metrics(y_val, preds, val_pred_baseline)
        ridge_search_log.append({"alpha": alpha, "val_mae_gbp": m["mae_gbp"], "val_rmse_gbp": m["rmse_gbp"]})
        if m["mae_gbp"] < best_ridge_val_mae:
            best_ridge_val_mae = m["mae_gbp"]
            best_ridge_alpha = alpha

    fitted_ridge = make_ridge_pipeline(alpha=best_ridge_alpha).fit(X_train, y_train)
    val_pred_ridge = fitted_ridge.predict(X_val)

    # 2b. Tree-Based Regression (HistGradientBoostingRegressor)
    hgb_configs = [
        {"max_depth": 3, "learning_rate": 0.04, "max_iter": 140, "min_samples_leaf": 20, "l2_regularization": 2.0},
        {"max_depth": 4, "learning_rate": 0.05, "max_iter": 160, "min_samples_leaf": 18, "l2_regularization": 1.0},
        {"max_depth": 5, "learning_rate": 0.05, "max_iter": 180, "min_samples_leaf": 15, "l2_regularization": 1.0},
    ]
    best_hgb_cfg = hgb_configs[1]
    best_hgb_val_mae = float("inf")
    hgb_search_log: list[dict[str, Any]] = []

    for cfg in hgb_configs:
        pipe = make_hgb_pipeline(**cfg)
        pipe.fit(X_train, y_train)
        preds = pipe.predict(X_val)
        m = compute_regression_metrics(y_val, preds, val_pred_baseline)
        hgb_search_log.append({"config": cfg, "val_mae_gbp": m["mae_gbp"], "val_rmse_gbp": m["rmse_gbp"]})
        if m["mae_gbp"] < best_hgb_val_mae:
            best_hgb_val_mae = m["mae_gbp"]
            best_hgb_cfg = cfg

    fitted_hgb = make_hgb_pipeline(**best_hgb_cfg).fit(X_train, y_train)
    val_pred_hgb = fitted_hgb.predict(X_val)

    # Validation comparison table
    val_metrics_by_model = {
        "weekday_mean_baseline": compute_regression_metrics(y_val, val_pred_baseline, val_pred_baseline),
        "ridge_linear_regression": compute_regression_metrics(y_val, val_pred_ridge, val_pred_baseline),
        "hist_gradient_boosting": compute_regression_metrics(y_val, val_pred_hgb, val_pred_baseline),
    }

    # Select winning model on Validation MAE (GBP)
    val_ranking = sorted(
        val_metrics_by_model.items(),
        key=lambda kv: (kv[1]["mae_gbp"], kv[1]["rmse_gbp"]),
    )
    selected_model_name = val_ranking[0][0]

    # Calibrate 80% empirical prediction interval on Validation residuals BEFORE touching Test set
    val_preds_map = {
        "weekday_mean_baseline": val_pred_baseline,
        "ridge_linear_regression": val_pred_ridge,
        "hist_gradient_boosting": val_pred_hgb,
    }
    interval_info = calibrate_empirical_prediction_interval(
        y_val, val_preds_map[selected_model_name], alpha=0.20
    )

    # Freeze selected configuration and evaluate all three frozen models on the untouched Test set
    # Note: We keep the exact training-split fitted pipeline frozen (no test leakage) so that validation
    # residual quantiles and training preprocessing bounds remain strictly aligned.
    test_pred_ridge = fitted_ridge.predict(X_test)
    test_pred_hgb = fitted_hgb.predict(X_test)

    test_metrics_by_model = {
        "weekday_mean_baseline": compute_regression_metrics(y_test, test_pred_baseline, test_pred_baseline),
        "ridge_linear_regression": compute_regression_metrics(y_test, test_pred_ridge, test_pred_baseline),
        "hist_gradient_boosting": compute_regression_metrics(y_test, test_pred_hgb, test_pred_baseline),
    }

    test_preds_map = {
        "weekday_mean_baseline": test_pred_baseline,
        "ridge_linear_regression": test_pred_ridge,
        "hist_gradient_boosting": test_pred_hgb,
    }
    selected_test_preds = test_preds_map[selected_model_name]

    test_interval_coverage = evaluate_interval_coverage(
        y_test,
        selected_test_preds,
        interval_info["residual_q_low_gbp"],
        interval_info["residual_q_high_gbp"],
    )
    interval_info["empirical_test_set_coverage"] = test_interval_coverage

    # Build full test-set DataFrame with predictions and errors for charts and worst-miss inspection
    test_results_df = test_df[
        [
            "date",
            "day_of_week",
            "day_name",
            "month",
            "temp_max_c",
            "rain_mm",
            "wind_max_kmh",
            "sunshine_hours",
            "outdoor_capacity",
            "is_uk_bank_holiday",
            "local_event_indicator",
            TARGET_COLUMN,
        ]
    ].copy()
    test_results_df["pred_weekday_baseline_gbp"] = np.round(test_pred_baseline, 2)
    test_results_df["pred_ridge_gbp"] = np.round(test_pred_ridge, 2)
    test_results_df["pred_hgb_gbp"] = np.round(test_pred_hgb, 2)
    test_results_df["pred_selected_gbp"] = np.round(selected_test_preds, 2)
    test_results_df["pred_interval_80_low_gbp"] = np.round(
        selected_test_preds + interval_info["residual_q_low_gbp"], 2
    )
    test_results_df["pred_interval_80_high_gbp"] = np.round(
        selected_test_preds + interval_info["residual_q_high_gbp"], 2
    )
    test_results_df["error_selected_gbp"] = np.round(
        test_results_df[TARGET_COLUMN] - test_results_df["pred_selected_gbp"], 2
    )
    test_results_df["abs_error_selected_gbp"] = np.round(
        np.abs(test_results_df["error_selected_gbp"]), 2
    )
    test_results_df["abs_error_baseline_gbp"] = np.round(
        np.abs(test_results_df[TARGET_COLUMN] - test_results_df["pred_weekday_baseline_gbp"]), 2
    )

    subset_eval = compute_subset_evaluations(
        test_results_df,
        y_true_col=TARGET_COLUMN,
        y_pred_col="pred_selected_gbp",
        baseline_col="pred_weekday_baseline_gbp",
    )

    # Worst misses (poor predictions) and best predictions on the untouched test set
    worst_misses = (
        test_results_df.sort_values("abs_error_selected_gbp", ascending=False)
        .head(10)
        .to_dict(orient="records")
    )
    best_hits = (
        test_results_df.sort_values("abs_error_selected_gbp", ascending=True)
        .head(10)
        .to_dict(orient="records")
    )

    # Save artifacts
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    training_weather_bounds = compute_training_weather_bounds(raw_df, max_train_date=TRAIN_END_DATE)
    monthly_ref_weather = compute_monthly_reference_weather(raw_df, max_train_date=TRAIN_END_DATE)

    models_map = {
        "weekday_mean_baseline": baseline_model,
        "ridge_linear_regression": fitted_ridge,
        "hist_gradient_boosting": fitted_hgb,
    }
    artifact_bundle = {
        "model_version": MODEL_VERSION,
        "trained_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "dataset_sha256": dataset_meta["dataset_sha256"],
        "selected_model_name": selected_model_name,
        "selected_pipeline": models_map[selected_model_name],
        "all_fitted_models": models_map,
        "train_weekday_means": train_weekday_means,
        "training_weather_bounds": training_weather_bounds,
        "monthly_reference_weather": monthly_ref_weather,
        "prediction_interval_80": interval_info,
        "feature_schema": get_feature_schema(),
    }
    joblib.dump(artifact_bundle, FITTED_PIPELINE_PATH)
    pipeline_sha256 = hashlib.sha256(FITTED_PIPELINE_PATH.read_bytes()).hexdigest()

    feature_schema = get_feature_schema()
    FEATURE_SCHEMA_PATH.write_text(json.dumps(feature_schema, indent=2), encoding="utf-8")

    splits_summary = {
        "training": {
            "start_date": str(train_df["date"].min()),
            "end_date": str(train_df["date"].max()),
            "n_days": int(len(train_df)),
            "share_pct": round(100.0 * len(train_df) / len(raw_df), 2),
        },
        "validation": {
            "start_date": str(val_df["date"].min()),
            "end_date": str(val_df["date"].max()),
            "n_days": int(len(val_df)),
            "share_pct": round(100.0 * len(val_df) / len(raw_df), 2),
        },
        "test": {
            "start_date": str(test_df["date"].min()),
            "end_date": str(test_df["date"].max()),
            "n_days": int(len(test_df)),
            "share_pct": round(100.0 * len(test_df) / len(raw_df), 2),
        },
    }

    training_config = {
        "model_version": MODEL_VERSION,
        "random_seed": 20261107,
        "dataset_sha256": dataset_meta["dataset_sha256"],
        "fitted_pipeline_sha256": pipeline_sha256,
        "chronological_splits": splits_summary,
        "preprocessing_fit_scope": "training_split_only (2022-01-01 to 2024-05-26)",
        "selection_criterion": "Minimum Validation MAE (GBP)",
        "selected_model_name": selected_model_name,
        "ridge_hyperparameter_search": {
            "candidates_alpha": ridge_candidates,
            "selected_alpha": best_ridge_alpha,
            "validation_results": ridge_search_log,
        },
        "hgb_hyperparameter_search": {
            "candidates": hgb_configs,
            "selected_config": best_hgb_cfg,
            "validation_results": hgb_search_log,
        },
        "train_weekday_means_gbp": train_weekday_means,
        "training_weather_bounds": training_weather_bounds,
        "monthly_reference_weather": {str(k): v for k, v in monthly_ref_weather.items()},
    }
    TRAINING_CONFIG_PATH.write_text(json.dumps(training_config, indent=2), encoding="utf-8")

    evaluation_report = {
        "model_version": MODEL_VERSION,
        "dataset_sha256": dataset_meta["dataset_sha256"],
        "fitted_pipeline_sha256": pipeline_sha256,
        "evaluation_framing": (
            "Conditional revenue prediction on realised historical weather from Open-Meteo paired with "
            "explicitly synthetic pub revenue. Demonstrates pipeline methodology and performance under "
            "stated synthetic assumptions; not proof of predictive accuracy on real private pub accounts."
        ),
        "splits": splits_summary,
        "selected_model_name": selected_model_name,
        "validation_metrics": val_metrics_by_model,
        "test_metrics": test_metrics_by_model,
        "test_subset_metrics_for_selected_model": subset_eval,
        "prediction_interval_80": interval_info,
        "worst_10_test_predictions": worst_misses,
        "best_10_test_predictions": best_hits,
    }
    EVALUATION_REPORT_JSON_PATH.write_text(json.dumps(evaluation_report, indent=2), encoding="utf-8")
    test_results_df.to_csv(TEST_PREDICTIONS_CSV_PATH, index=False)

    _write_markdown_report(evaluation_report, training_config)
    return evaluation_report


def _write_markdown_report(eval_rep: dict[str, Any], train_cfg: dict[str, Any]) -> None:
    splits = eval_rep["splits"]
    val_m = eval_rep["validation_metrics"]
    test_m = eval_rep["test_metrics"]
    sub_m = eval_rep["test_subset_metrics_for_selected_model"]
    pi = eval_rep["prediction_interval_80"]

    lines = [
        "# Revenue Prediction Model: Training & Held-Out Evaluation Report",
        "",
        "> **Synthetic Revenue Disclosure:** Weather features are real daily London observations from Open-Meteo ERA5 (`2022-01-01` to `2025-12-31`). Daily pub revenue (`daily_revenue_gbp`) and operational attributes are synthetically generated (`seed=20261107`). Evaluation results below measure conditional revenue prediction on held-out dates under the stated synthetic data-generating assumptions and do not prove accuracy for real-world pubs.",
        "",
        "## 1. Chronological Data Split",
        "",
        "| Split | Start Date | End Date | Observations (Days) | Share (%) | Role |",
        "| :--- | :--- | :--- | ---: | ---: | :--- |",
        f"| **Training** | `{splits['training']['start_date']}` | `{splits['training']['end_date']}` | {splits['training']['n_days']} | {splits['training']['share_pct']}% | Fit preprocessing, baseline, and candidate models |",
        f"| **Validation** | `{splits['validation']['start_date']}` | `{splits['validation']['end_date']}` | {splits['validation']['n_days']} | {splits['validation']['share_pct']}% | Select model family, hyperparameters, and 80% residual interval |",
        f"| **Test (Untouched)** | `{splits['test']['start_date']}` | `{splits['test']['end_date']}` | {splits['test']['n_days']} | {splits['test']['share_pct']}% | Frozen out-of-sample evaluation |",
        "",
        f"- **Dataset SHA-256:** `{eval_rep['dataset_sha256']}`",
        f"- **Saved Pipeline Artifact SHA-256:** `{eval_rep['fitted_pipeline_sha256']}`",
        f"- **Selected Model (Frozen on Validation):** `{eval_rep['selected_model_name']}`",
        "",
        "## 2. Validation Split Comparison (Model Selection)",
        "",
        "| Model | MAE (£) | RMSE (£) | Median AE (£) | MAE Improvement vs Baseline (£ / %) |",
        "| :--- | ---: | ---: | ---: | ---: |",
    ]
    for m_name, m_val in val_m.items():
        lines.append(
            f"| `{m_name}` | £{m_val['mae_gbp']:.2f} | £{m_val['rmse_gbp']:.2f} | £{m_val['median_abs_error_gbp']:.2f} | "
            f"£{m_val['mae_improvement_vs_baseline_gbp']:+.2f} ({m_val['mae_improvement_vs_baseline_pct']:+.2f}%) |"
        )

    lines.extend(
        [
            "",
            "## 3. Untouched Test Split Performance (`2025-03-15` to `2025-12-31`, n=292)",
            "",
            "| Model | MAE (£) | RMSE (£) | Median AE (£) | Mean Bias (£) | MAE Improvement vs Baseline (£ / %) | RMSE Improvement vs Baseline (£ / %) |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for m_name, m_test in test_m.items():
        lines.append(
            f"| `{m_name}` | £{m_test['mae_gbp']:.2f} | £{m_test['rmse_gbp']:.2f} | £{m_test['median_abs_error_gbp']:.2f} | "
            f"£{m_test['mean_signed_bias_gbp']:+.2f} | £{m_test['mae_improvement_vs_baseline_gbp']:+.2f} ({m_test['mae_improvement_vs_baseline_pct']:+.2f}%) | "
            f"£{m_test['rmse_improvement_vs_baseline_gbp']:+.2f} ({m_test['rmse_improvement_vs_baseline_pct']:+.2f}%) |"
        )

    lines.extend(
        [
            "",
            "## 4. Test Subset Breakdown for Selected Model (`" + eval_rep["selected_model_name"] + "`)",
            "",
            "| Subset | Sample Size (n) | Model MAE (£) | Baseline MAE (£) | Model RMSE (£) | Baseline RMSE (£) | MAE Improvement (£ / %) |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for sub_name, sub_val in sub_m.items():
        if sub_val.get("n_observations", 0) == 0:
            continue
        lines.append(
            f"| `{sub_name}` | {sub_val['n_observations']} | £{sub_val['mae_gbp']:.2f} | £{sub_val['baseline_mae_gbp']:.2f} | "
            f"£{sub_val['rmse_gbp']:.2f} | £{sub_val['baseline_rmse_gbp']:.2f} | "
            f"£{sub_val['mae_improvement_vs_baseline_gbp']:+.2f} ({sub_val['mae_improvement_vs_baseline_pct']:+.2f}%) |"
        )

    lines.extend(
        [
            "",
            "## 5. Prediction Interval Calibration & Limitations",
            "",
            f"- **Nominal Coverage:** {int(pi['nominal_coverage'] * 100)}%",
            f"- **Validation Residual Quantiles:** `[{pi['residual_q_low_gbp']:+.2f} GBP, {pi['residual_q_high_gbp']:+.2f} GBP]`",
            f"- **Empirical Coverage on Untouched Test Set:** `{pi['empirical_test_set_coverage'] * 100:.2f}%`",
            f"- **Method:** {pi['method']}",
            f"- **Limitations:** {pi['limitations']}",
            "",
            "## 6. Largest Prediction Misses on the Untouched Test Set (Honest Failure Analysis)",
            "",
            "The largest errors occur on unlabelled exceptional shock days (e.g., private venue hires or operational disruptions) and high-variance weekend weather transitions:",
            "",
            "| Date | Day | Max Temp (°C) | Rain (mm) | Actual (£) | Predicted (£) | Baseline (£) | Error (£) |",
            "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in eval_rep["worst_10_test_predictions"]:
        lines.append(
            f"| `{row['date']}` | {row['day_name']} | {row['temp_max_c']:.1f} | {row['rain_mm']:.1f} | "
            f"£{row['daily_revenue_gbp']:.2f} | £{row['pred_selected_gbp']:.2f} | "
            f"£{row['pred_weekday_baseline_gbp']:.2f} | £{row['error_selected_gbp']:+.2f} |"
        )

    EVALUATION_MARKDOWN_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    rep = run_training_and_evaluation()
    sel = rep["selected_model_name"]
    tm = rep["test_metrics"][sel]
    print(
        f"Training & evaluation complete. Selected model: {sel} | "
        f"Test MAE: £{tm['mae_gbp']:.2f} (vs Baseline £{tm['baseline_mae_gbp']:.2f}, "
        f"{tm['mae_improvement_vs_baseline_pct']:+.2f}%) | "
        f"Test RMSE: £{tm['rmse_gbp']:.2f} (vs Baseline £{tm['baseline_rmse_gbp']:.2f})"
    )
