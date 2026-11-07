# Revenue Prediction Model: Training & Held-Out Evaluation Report

> **Synthetic Revenue Disclosure:** Weather features are real daily London observations from Open-Meteo ERA5 (`2022-01-01` to `2025-12-31`). Daily pub revenue (`daily_revenue_gbp`) and operational attributes are synthetically generated (`seed=20261107`). Evaluation results below measure conditional revenue prediction on held-out dates under the stated synthetic data-generating assumptions and do not prove accuracy for real-world pubs.

## 1. Chronological Data Split

| Split | Start Date | End Date | Observations (Days) | Share (%) | Role |
| :--- | :--- | :--- | ---: | ---: | :--- |
| **Training** | `2022-01-01` | `2024-05-26` | 877 | 60.03% | Fit preprocessing, baseline, and candidate models |
| **Validation** | `2024-05-27` | `2025-03-14` | 292 | 19.99% | Select model family, hyperparameters, and 80% residual interval |
| **Test (Untouched)** | `2025-03-15` | `2025-12-31` | 292 | 19.99% | Frozen out-of-sample evaluation |

- **Dataset SHA-256:** `5d05ae9a2d9a4eaf4b676eca0a90d573dbd0e31bc4bd95c3274edf7216a9e8ab`
- **Saved Pipeline Artifact SHA-256:** `b38d3076b5db3fcb4e122180c8e71ba7fc6762a48d100027c2465177d8014e12`
- **Selected Model (Frozen on Validation):** `hist_gradient_boosting`

## 2. Validation Split Comparison (Model Selection)

| Model | MAE (£) | RMSE (£) | Median AE (£) | MAE Improvement vs Baseline (£ / %) |
| :--- | ---: | ---: | ---: | ---: |
| `weekday_mean_baseline` | £1063.12 | £1301.50 | £877.31 | £+0.00 (+0.00%) |
| `ridge_linear_regression` | £362.37 | £474.41 | £286.44 | £+700.75 (+65.91%) |
| `hist_gradient_boosting` | £244.46 | £308.87 | £212.34 | £+818.66 (+77.01%) |

## 3. Untouched Test Split Performance (`2025-03-15` to `2025-12-31`, n=292)

| Model | MAE (£) | RMSE (£) | Median AE (£) | Mean Bias (£) | MAE Improvement vs Baseline (£ / %) | RMSE Improvement vs Baseline (£ / %) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `weekday_mean_baseline` | £1301.56 | £1634.44 | £1011.24 | £+911.22 | £+0.00 (+0.00%) | £+0.00 (+0.00%) |
| `ridge_linear_regression` | £479.41 | £626.93 | £355.07 | £+273.04 | £+822.14 (+63.17%) | £+1007.51 (+61.64%) |
| `hist_gradient_boosting` | £340.18 | £455.17 | £264.74 | £+221.30 | £+961.37 (+73.86%) | £+1179.27 (+72.15%) |

## 4. Test Subset Breakdown for Selected Model (`hist_gradient_boosting`)

| Subset | Sample Size (n) | Model MAE (£) | Baseline MAE (£) | Model RMSE (£) | Baseline RMSE (£) | MAE Improvement (£ / %) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `all_days` | 292 | £340.18 | £1301.56 | £455.17 | £1634.44 | £+961.37 (+73.86%) |
| `rainy_days_rain_ge_2mm` | 59 | £259.02 | £700.03 | £368.04 | £823.55 | £+441.02 (+63.00%) |
| `heavy_rain_days_rain_ge_8mm` | 17 | £363.43 | £1035.30 | £513.42 | £1108.34 | £+671.87 (+64.90%) |
| `dry_warm_days_temp_ge_18c_rain_lt_1mm` | 104 | £408.92 | £2313.66 | £512.97 | £2458.11 | £+1904.74 (+82.33%) |
| `weekends_fri_sat_sun` | 125 | £421.08 | £1672.83 | £518.25 | £2014.39 | £+1251.74 (+74.83%) |
| `weekdays_mon_to_thu` | 167 | £279.63 | £1023.66 | £401.53 | £1278.16 | £+744.03 (+72.68%) |
| `uk_bank_holidays` | 7 | £532.44 | £1815.09 | £727.18 | £2378.65 | £+1282.64 (+70.67%) |

## 5. Prediction Interval Calibration & Limitations

- **Nominal Coverage:** 80%
- **Validation Residual Quantiles:** `[-315.68 GBP, +453.59 GBP]`
- **Empirical Coverage on Untouched Test Set:** `69.86%`
- **Method:** Split-conformal / empirical residual quantiles (10th and 90th percentiles of validation-set residuals y_true - y_hat) added to point predictions.
- **Limitations:** Assumes exchangeability of residual distribution between validation and target periods; interval width is homoskedastic and may under-cover extreme unlabelled one-off events (such as unannounced street closures or private venue buyouts) or out-of-range weather.

## 6. Largest Prediction Misses on the Untouched Test Set (Honest Failure Analysis)

The largest errors occur on unlabelled exceptional shock days (e.g., private venue hires or operational disruptions) and high-variance weekend weather transitions:

| Date | Day | Max Temp (°C) | Rain (mm) | Actual (£) | Predicted (£) | Baseline (£) | Error (£) |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `2025-08-01` | Friday | 19.8 | 1.2 | £8122.80 | £5970.30 | £4828.80 | £+2152.50 |
| `2025-08-26` | Tuesday | 25.4 | 0.2 | £5743.58 | £3940.86 | £2285.19 | £+1802.72 |
| `2025-12-18` | Thursday | 12.7 | 17.7 | £3824.31 | £2207.43 | £3062.28 | £+1616.88 |
| `2025-08-25` | Monday | 26.0 | 0.0 | £7100.64 | £5643.10 | £2392.21 | £+1457.54 |
| `2025-11-05` | Wednesday | 17.2 | 0.1 | £3835.20 | £2413.60 | £2551.42 | £+1421.60 |
| `2025-09-05` | Friday | 20.7 | 0.0 | £8036.60 | £6733.59 | £4828.80 | £+1303.01 |
| `2025-11-18` | Tuesday | 6.9 | 0.1 | £2844.94 | £1833.11 | £2285.19 | £+1011.83 |
| `2025-10-10` | Friday | 15.8 | 0.1 | £5835.97 | £4828.30 | £4828.80 | £+1007.67 |
| `2025-10-04` | Saturday | 16.7 | 3.6 | £5268.85 | £4267.05 | £5365.54 | £+1001.80 |
| `2025-03-30` | Sunday | 15.9 | 0.0 | £6076.24 | £5086.57 | £4123.50 | £+989.67 |
