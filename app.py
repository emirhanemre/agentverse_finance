"""Browser interface for UK Pub Weather Exposure & Polymarket Paper Hedge Assessment.

Run locally with:
    streamlit run app.py

Provides four views with descriptive labels and no product branding:
- View A: Data and model
- View B: Business assessment
- View C: Agent assessment
- View D: Approval and results
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pandas as pd
import streamlit as st

from src.agent import (
    check_gemini_server_access,
    infer_exposure_driver,
    run_deterministic_matching_strategy,
    run_gemini_agent_assessment,
)
from src.agent_eval import build_labelled_test_fixtures
from src.business_data import load_dataset_metadata
from src.inference import (
    compare_weather_scenarios_for_date,
    get_reference_weather_for_date,
    load_saved_model_bundle,
)
from src.paper_execution import PaperTradingStore
from src.polymarket_client import PolymarketConnector
from src.training import (
    EVALUATION_REPORT_JSON_PATH,
    TEST_PREDICTIONS_CSV_PATH,
    TRAINING_CONFIG_PATH,
)

ROOT = Path(__file__).resolve().parent
AGENT_EVAL_REPORT_PATH = ROOT / "artifacts" / "models" / "agent_evaluation_report.json"

st.set_page_config(
    page_title="UK Pub Weather Exposure & Polymarket Hedge Assessment",
    layout="wide",
)


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_store() -> PaperTradingStore:
    return PaperTradingStore()


def render_header_and_disclosures() -> tuple[bool, bool]:
    st.title("UK Pub Weather Exposure & Polymarket Paper Hedge Assessment")
    st.caption(
        "Decision support for an independent UK pub with outdoor seating: "
        "“How exposed is my business to the forecast weather, and would any available Polymarket contract "
        "meaningfully offset that exposure within my budget?”"
    )

    gem_access = check_gemini_server_access()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(
            "**Data Provenance Badge**\n\n"
            "- **Weather Data:** `REAL` (Open-Meteo ERA5 London daily archive, 2022–2025, CC-BY 4.0)\n"
            "- **Pub Revenue Data:** `SYNTHETIC` (`seed=20261107`, fictional London SE1 pub). "
            "Demonstrates pipeline methodology under stated synthetic assumptions; not real pub accounts."
        )
    with col2:
        include_test_fixtures = st.checkbox(
            "Include labelled synthetic test fixtures (`[SYNTHETIC TEST FIXTURE]`) in market catalog",
            value=False,
            help=(
                "Keep unchecked to search only authentic cached/live Polymarket contracts. "
                "Check to include explicitly labelled test fixtures (e.g. `TEST_FIX_LONDON_RAIN_2025_09_06`) "
                "to test the positive paper-trade approval workflow and risk-control triggers."
            ),
        )
        allow_live_refresh = st.checkbox(
            "Attempt live Polymarket CLOB order-book refresh before snapshot fallback",
            value=False,
            help="Queries public read-only Polymarket endpoints if internet is available; falls back to saved authentic snapshots.",
        )
    with col3:
        if gem_access["available"]:
            st.success(
                f"**Gemini Server Access: READY**\n\n"
                f"- **Model:** `{gem_access['model_id']}`\n"
                f"- **Auth:** {gem_access['auth_method']}\n"
                f"- Credentials remain strictly on the server."
            )
        else:
            st.warning(
                f"**Live Gemini Server Integration: BLOCKED**\n\n"
                f"- **Model:** `{gem_access['model_id']}`\n"
                f"- **Status:** `{gem_access['status']}`\n"
                f"- **Why:** {gem_access['message']}"
            )
            with st.expander("Short question for hackathon organisers (Section 5)"):
                st.code(gem_access.get("organiser_question", ""), language="text")

    return include_test_fixtures, allow_live_refresh


def render_view_a_data_and_model() -> None:
    st.header("A. Data and Model")

    dataset_meta = load_dataset_metadata()
    eval_rep = load_json_file(EVALUATION_REPORT_JSON_PATH)
    train_cfg = load_json_file(TRAINING_CONFIG_PATH)

    st.warning(
        "**Prominent Synthetic Data Disclosure:** Daily pub revenue (`daily_revenue_gbp`), seating capacities, "
        "opening hours, and local event flags are synthetically generated (`src/business_data.py`, `seed=20261107`). "
        "Daily weather observations (`temp_max_c`, `rain_mm`, `wind_max_kmh`, `sunshine_hours`) are real historical "
        "observations for London, UK (`51.5074, -0.1278`) from Open-Meteo ERA5 (`2022-01-01` to `2025-12-31`). "
        "Test results below measure conditional revenue prediction on held-out dates under synthetic business assumptions "
        "and never imply predictive accuracy for real pubs."
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Saved Model Version", eval_rep.get("model_version", "N/A"))
    m2.metric("Selected Model (Validation)", eval_rep.get("selected_model_name", "N/A"))
    sel_name = eval_rep.get("selected_model_name", "hist_gradient_boosting")
    sel_test = eval_rep.get("test_metrics", {}).get(sel_name, {})
    m3.metric(
        "Untouched Test MAE (£)",
        f"£{sel_test.get('mae_gbp', 0.0):.2f}",
        delta=f"-£{sel_test.get('mae_improvement_vs_baseline_gbp', 0.0):.2f} vs baseline ({sel_test.get('mae_improvement_vs_baseline_pct', 0.0):+.1f}%)",
        delta_color="normal",
    )
    m4.metric(
        "Untouched Test RMSE (£)",
        f"£{sel_test.get('rmse_gbp', 0.0):.2f}",
        delta=f"-£{sel_test.get('rmse_improvement_vs_baseline_gbp', 0.0):.2f} vs baseline",
        delta_color="normal",
    )

    st.subheader("1. Chronological Data Split & Fingerprints")
    splits = eval_rep.get("splits", {})
    if splits:
        split_rows = []
        for s_name, s_info in splits.items():
            split_rows.append(
                {
                    "Split": s_name.capitalize(),
                    "Start Date": s_info["start_date"],
                    "End Date": s_info["end_date"],
                    "Observations (Days)": s_info["n_days"],
                    "Share (%)": f"{s_info['share_pct']:.2f}%",
                }
            )
        st.table(pd.DataFrame(split_rows))

    st.caption(
        f"**Dataset SHA-256:** `{eval_rep.get('dataset_sha256', '')}` | "
        f"**Saved Fitted Pipeline SHA-256:** `{eval_rep.get('fitted_pipeline_sha256', '')}` | "
        f"**Preprocessing Fit Scope:** `{train_cfg.get('preprocessing_fit_scope', '')}`"
    )

    st.subheader("2. Candidate Models Compared (Validation vs Untouched Test Split)")
    comp_rows = []
    for model_key in ["weekday_mean_baseline", "ridge_linear_regression", "hist_gradient_boosting"]:
        vm = eval_rep.get("validation_metrics", {}).get(model_key, {})
        tm = eval_rep.get("test_metrics", {}).get(model_key, {})
        if vm and tm:
            comp_rows.append(
                {
                    "Model": model_key,
                    "Selected on Validation": "YES (Frozen)" if model_key == sel_name else "No",
                    "Validation MAE (£)": f"£{vm['mae_gbp']:.2f}",
                    "Validation RMSE (£)": f"£{vm['rmse_gbp']:.2f}",
                    "Test MAE (£)": f"£{tm['mae_gbp']:.2f}",
                    "Test RMSE (£)": f"£{tm['rmse_gbp']:.2f}",
                    "Test Median AE (£)": f"£{tm['median_abs_error_gbp']:.2f}",
                    "Test MAE Improvement vs Baseline (£ / %)": (
                        f"£{tm['mae_improvement_vs_baseline_gbp']:+.2f} ({tm['mae_improvement_vs_baseline_pct']:+.2f}%)"
                    ),
                }
            )
    st.dataframe(pd.DataFrame(comp_rows), use_container_width=True)

    if TEST_PREDICTIONS_CSV_PATH.exists():
        test_df = pd.read_csv(TEST_PREDICTIONS_CSV_PATH)
        st.subheader("3. Untouched Test Set: Actual vs Predicted Daily Revenue Over Time (`2025-03-15` to `2025-12-31`)")
        chart_df = test_df.set_index("date")[
            ["daily_revenue_gbp", "pred_selected_gbp", "pred_weekday_baseline_gbp"]
        ].rename(
            columns={
                "daily_revenue_gbp": "Actual Revenue (£, Synthetic)",
                "pred_selected_gbp": f"Selected Model Prediction (£, {sel_name})",
                "pred_weekday_baseline_gbp": "Weekday Historical Mean Baseline (£)",
            }
        )
        st.line_chart(chart_df)

    st.subheader("4. Subset Error Breakdown on Untouched Test Split (Including Rainy Days)")
    sub_metrics = eval_rep.get("test_subset_metrics_for_selected_model", {})
    if sub_metrics:
        sub_rows = []
        for s_key, s_val in sub_metrics.items():
            if s_val.get("n_observations", 0) == 0:
                continue
            sub_rows.append(
                {
                    "Subset": s_key,
                    "Sample Size (n)": s_val["n_observations"],
                    "Selected Model MAE (£)": f"£{s_val['mae_gbp']:.2f}",
                    "Baseline MAE (£)": f"£{s_val['baseline_mae_gbp']:.2f}",
                    "Selected Model RMSE (£)": f"£{s_val['rmse_gbp']:.2f}",
                    "Baseline RMSE (£)": f"£{s_val['baseline_rmse_gbp']:.2f}",
                    "MAE Improvement vs Baseline (£ / %)": (
                        f"£{s_val['mae_improvement_vs_baseline_gbp']:+.2f} ({s_val['mae_improvement_vs_baseline_pct']:+.2f}%)"
                    ),
                }
            )
        st.dataframe(pd.DataFrame(sub_rows), use_container_width=True)

    pi = eval_rep.get("prediction_interval_80", {})
    if pi:
        st.subheader("5. Prediction Interval Method & Honest Failure Analysis")
        st.markdown(
            f"- **Prediction Interval Method:** {pi.get('method')}\n"
            f"- **Validation Residual Quantiles (10th / 90th):** `[{pi.get('residual_q_low_gbp', 0):+.2f} GBP, {pi.get('residual_q_high_gbp', 0):+.2f} GBP]`\n"
            f"- **Empirical Coverage on Untouched Test Set:** `{pi.get('empirical_test_set_coverage', 0) * 100:.2f}%` (vs `{int(pi.get('nominal_coverage', 0.8) * 100)}%` nominal)\n"
            f"- **Limitations:** {pi.get('limitations')}"
        )

    c_worst, c_best = st.columns(2)
    with c_worst:
        st.markdown("**10 Largest Prediction Misses on Test Set (Poor Predictions)**")
        worst_df = pd.DataFrame(eval_rep.get("worst_10_test_predictions", []))
        if not worst_df.empty:
            st.dataframe(
                worst_df[
                    [
                        "date",
                        "day_name",
                        "temp_max_c",
                        "rain_mm",
                        "daily_revenue_gbp",
                        "pred_selected_gbp",
                        "error_selected_gbp",
                    ]
                ],
                use_container_width=True,
            )
    with c_best:
        st.markdown("**10 Closest Predictions on Test Set**")
        best_df = pd.DataFrame(eval_rep.get("best_10_test_predictions", []))
        if not best_df.empty:
            st.dataframe(
                best_df[
                    [
                        "date",
                        "day_name",
                        "temp_max_c",
                        "rain_mm",
                        "daily_revenue_gbp",
                        "pred_selected_gbp",
                        "error_selected_gbp",
                    ]
                ],
                use_container_width=True,
            )

    with st.expander("Inspect Data Generation Assumptions & Feature Schema"):
        st.json(
            {
                "assumptions_and_mechanics": dataset_meta.get("assumptions_and_mechanics", []),
                "units": dataset_meta.get("units", {}),
                "feature_schema": load_saved_model_bundle()["feature_schema"],
            }
        )


def render_view_b_business_assessment() -> dict[str, Any]:
    st.header("B. Business Assessment (Weather Scenario Exposure)")
    st.markdown(
        "Configure the pub's target operating date, forecast/adverse weather scenario, and paper hedging budget. "
        "The saved model compares predicted revenue under the adverse scenario against the seasonal dry reference scenario."
    )

    presets = {
        "Preset 1: Wet Summer Saturday in London (2025-07-19 | Real Polymarket Catalog -> No Suitable Live Hedge)": {
            "date": "2025-07-19",
            "temp_max_c": 16.5,
            "rain_mm": 14.0,
            "wind_max_kmh": 30.0,
            "sunshine_hours": 0.5,
            "outdoor_capacity": 70,
            "budget_gbp": 180.0,
        },
        "Preset 2: Historical London Replay — Rainy Day vs London Temp Contract (2025-01-23 | Basis Risk Rejection)": {
            "date": "2025-01-23",
            "temp_max_c": 11.5,
            "rain_mm": 12.0,
            "wind_max_kmh": 26.0,
            "sunshine_hours": 0.0,
            "outdoor_capacity": 42,
            "budget_gbp": 150.0,
        },
        "Preset 3: Controlled Simulation — Suitable London Rain Contract (2025-09-06 | Enable Test Fixtures Above)": {
            "date": "2025-09-06",
            "temp_max_c": 15.0,
            "rain_mm": 14.0,
            "wind_max_kmh": 26.0,
            "sunshine_hours": 0.5,
            "outdoor_capacity": 70,
            "budget_gbp": 180.0,
        },
        "Preset 4: Extreme Out-of-Range Weather Scenario (2025-09-20 | 95mm Rain & 41.5°C Warning)": {
            "date": "2025-09-20",
            "temp_max_c": 41.5,
            "rain_mm": 95.0,
            "wind_max_kmh": 35.0,
            "sunshine_hours": 0.0,
            "outdoor_capacity": 70,
            "budget_gbp": 180.0,
        },
        "Preset 5: Single-Contract Budget Limit Breach (2025-09-06 | £750 Budget > £500 Risk Limit)": {
            "date": "2025-09-06",
            "temp_max_c": 15.0,
            "rain_mm": 14.0,
            "wind_max_kmh": 26.0,
            "sunshine_hours": 0.5,
            "outdoor_capacity": 70,
            "budget_gbp": 750.0,
        },
    }

    selected_preset_label = st.selectbox("Quick Scenario Preset (or customize any input below):", list(presets.keys()))
    preset = presets[selected_preset_label]

    c1, c2, c3 = st.columns(3)
    with c1:
        target_date = st.text_input("Target Operating Date (YYYY-MM-DD)", value=preset["date"])
        budget_gbp = st.number_input(
            "Paper Hedge Budget (£ GBP)",
            min_value=10.0,
            max_value=2000.0,
            value=float(preset["budget_gbp"]),
            step=10.0,
        )
        outdoor_capacity = st.number_input(
            "Usable Outdoor Beer Garden Seats",
            min_value=0,
            max_value=200,
            value=int(preset["outdoor_capacity"]),
            step=5,
        )
    with c2:
        adv_temp_max = st.number_input(
            "Forecast / Scenario Max Temperature (°C)",
            min_value=-15.0,
            max_value=48.0,
            value=float(preset["temp_max_c"]),
            step=0.5,
        )
        adv_rain_mm = st.number_input(
            "Forecast / Scenario Daily Rainfall (mm)",
            min_value=0.0,
            max_value=150.0,
            value=float(preset["rain_mm"]),
            step=1.0,
        )
    with c3:
        adv_wind_kmh = st.number_input(
            "Forecast / Scenario Max Wind Speed (km/h)",
            min_value=0.0,
            max_value=120.0,
            value=float(preset["wind_max_kmh"]),
            step=2.0,
        )
        adv_sunshine_h = st.number_input(
            "Forecast / Scenario Sunshine Duration (hours)",
            min_value=0.0,
            max_value=16.0,
            value=float(preset["sunshine_hours"]),
            step=0.5,
        )

    adverse_weather = {
        "temp_max_c": float(adv_temp_max),
        "temp_min_c": float(adv_temp_max) - 6.0,
        "temp_mean_c": float(adv_temp_max) - 3.0,
        "precipitation_mm": float(adv_rain_mm),
        "rain_mm": float(adv_rain_mm),
        "wind_max_kmh": float(adv_wind_kmh),
        "sunshine_hours": float(adv_sunshine_h),
    }

    try:
        ref_weather = get_reference_weather_for_date(target_date)
        comp = compare_weather_scenarios_for_date(
            target_date=target_date,
            adverse_weather=adverse_weather,
            reference_weather=ref_weather,
            outdoor_capacity=int(outdoor_capacity),
        )
    except Exception as exc:
        st.error(f"Could not compute scenario comparison: {exc}")
        return {
            "target_date": target_date,
            "budget_gbp": budget_gbp,
            "outdoor_capacity": outdoor_capacity,
            "adverse_weather": adverse_weather,
            "comparison": None,
        }

    st.subheader("Model-Based Scenario Exposure Estimate")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Forecast / Adverse Scenario Revenue",
        f"£{comp.scenario_predicted_revenue_gbp:,.2f}",
        help=f"80% Prediction Interval: [£{comp.scenario_prediction.prediction_interval_80_low_gbp:,.2f}, £{comp.scenario_prediction.prediction_interval_80_high_gbp:,.2f}]",
    )
    k2.metric(
        "Seasonal Dry Reference Revenue",
        f"£{comp.reference_predicted_revenue_gbp:,.2f}",
        help=f"80% Prediction Interval: [£{comp.reference_prediction.prediction_interval_80_low_gbp:,.2f}, £{comp.reference_prediction.prediction_interval_80_high_gbp:,.2f}]",
    )
    k3.metric(
        "Estimated Scenario Difference",
        f"£{comp.estimated_difference_gbp:+,.2f}",
        delta=f"Downside exposure: £{comp.estimated_downside_loss_gbp:,.2f}",
        delta_color="inverse",
    )
    k4.metric(
        "Weekday Historical Baseline",
        f"£{comp.scenario_prediction.baseline_weekday_revenue_gbp:,.2f}",
        help="Simple baseline predicting training-set mean revenue for this weekday regardless of weather.",
    )

    if comp.scenario_prediction.is_out_of_training_range:
        st.error(
            "**Out-of-Training-Range Weather Alert:**\n- "
            + "\n- ".join(comp.scenario_prediction.out_of_range_reasons)
            + "\n\nPredictions outside the observed training domain carry high extrapolation uncertainty."
        )
    else:
        st.success(
            "All scenario weather inputs fall within the observed 2022–2024 London training data distribution."
        )

    comp_table = pd.DataFrame(
        [
            {
                "Scenario": comp.scenario_label,
                "Max Temp (°C)": adverse_weather["temp_max_c"],
                "Rain (mm)": adverse_weather["rain_mm"],
                "Wind (km/h)": adverse_weather["wind_max_kmh"],
                "Sunshine (h)": adverse_weather["sunshine_hours"],
                "Predicted Revenue (£)": f"£{comp.scenario_predicted_revenue_gbp:,.2f}",
                "80% Interval Low (£)": f"£{comp.scenario_prediction.prediction_interval_80_low_gbp:,.2f}",
                "80% Interval High (£)": f"£{comp.scenario_prediction.prediction_interval_80_high_gbp:,.2f}",
            },
            {
                "Scenario": comp.reference_label,
                "Max Temp (°C)": ref_weather["temp_max_c"],
                "Rain (mm)": ref_weather["rain_mm"],
                "Wind (km/h)": ref_weather["wind_max_kmh"],
                "Sunshine (h)": ref_weather["sunshine_hours"],
                "Predicted Revenue (£)": f"£{comp.reference_predicted_revenue_gbp:,.2f}",
                "80% Interval Low (£)": f"£{comp.reference_prediction.prediction_interval_80_low_gbp:,.2f}",
                "80% Interval High (£)": f"£{comp.reference_prediction.prediction_interval_80_high_gbp:,.2f}",
            },
        ]
    )
    st.table(comp_table)

    st.info(
        f"**Framing & Uncertainty Note:** {comp.framing_note}\n\n"
        + "\n".join(f"- {a}" for a in comp.assumptions)
    )

    return {
        "target_date": target_date,
        "budget_gbp": float(budget_gbp),
        "outdoor_capacity": int(outdoor_capacity),
        "adverse_weather": adverse_weather,
        "comparison": comp,
    }


def render_view_c_agent_assessment(
    scenario_ctx: dict[str, Any],
    include_test_fixtures: bool,
    allow_live_refresh: bool,
) -> None:
    st.header("C. Agent Assessment & Polymarket Contract Inspection")

    gem_access = check_gemini_server_access()
    store = get_store()
    fixtures = build_labelled_test_fixtures() if include_test_fixtures else []
    connector = PolymarketConnector(allow_live_network=allow_live_refresh, extra_fixtures=fixtures)

    driver = infer_exposure_driver(scenario_ctx["adverse_weather"])
    st.markdown(
        f"**Target Date:** `{scenario_ctx['target_date']}` | "
        f"**Paper Budget:** `£{scenario_ctx['budget_gbp']:.2f}` | "
        f"**Inferred Primary Exposure Driver:** `{driver}` | "
        f"**Catalog Mode:** `{'Authentic Polymarket + Labelled Test Fixtures' if include_test_fixtures else 'Authentic Polymarket Catalog Only'}`"
    )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        run_gemini_clicked = st.button(
            "Run assessment (Server-Side Gemini 4 Argon Agent)",
            type="primary",
            use_container_width=True,
        )
    with col_btn2:
        run_det_clicked = st.button(
            "Run assessment (Deterministic Contract-Matching Comparator)",
            use_container_width=True,
        )

    if run_gemini_clicked:
        with st.spinner("Running server-side Gemini 4 Argon tool-calling assessment..."):
            res = run_gemini_agent_assessment(
                target_date=scenario_ctx["target_date"],
                adverse_weather=scenario_ctx["adverse_weather"],
                budget_gbp=scenario_ctx["budget_gbp"],
                connector=connector,
                store=store,
                outdoor_capacity=scenario_ctx["outdoor_capacity"],
            )
            st.session_state["last_assessment_result"] = res

    if run_det_clicked:
        with st.spinner("Running deterministic contract-matching comparator across the 10 domain tools..."):
            res = run_deterministic_matching_strategy(
                target_date=scenario_ctx["target_date"],
                adverse_weather=scenario_ctx["adverse_weather"],
                budget_gbp=scenario_ctx["budget_gbp"],
                connector=connector,
                store=store,
                outdoor_capacity=scenario_ctx["outdoor_capacity"],
            )
            st.session_state["last_assessment_result"] = res

    last_res = st.session_state.get("last_assessment_result")
    if last_res:
        st.subheader(f"Assessment Result (`{last_res.get('execution_mode')}`)")
        if last_res.get("live_agent_blocked"):
            st.error(
                "**Live Gemini 4 Argon Server Call Blocked:**\n\n"
                f"{last_res['access_check']['message']}\n\n"
                "We never disguise a scripted or mocked agent as a functioning Gemini integration. "
                "To inspect the full 10-tool pipeline, contract rejection logic, financial calculations, "
                "and paper approval controls right now without an API key, click "
                "**Run assessment (Deterministic Contract-Matching Comparator)** above, or add `GEMINI_API_KEY` to `.env`."
            )
        elif last_res.get("error"):
            st.error(f"Agent execution error: {last_res['error']}")
        else:
            prop = last_res.get("proposal")
            status_val = last_res.get("status", "no_suitable_hedge")
            if status_val == "recommend_paper_hedge":
                st.success(f"**Final Structured Decision:** `{status_val}` (Proposal ID: `{prop.proposal_id if prop else 'N/A'}`)")
            elif status_val == "no_suitable_hedge":
                st.warning(f"**Final Structured Decision:** `{status_val}` (Proposal ID: `{prop.proposal_id if prop else 'N/A'}`)")
            else:
                st.info(f"**Final Structured Decision:** `{status_val}`")

            if prop:
                st.markdown(f"**Decision Explanation:**\n\n{prop.explanation}")
                st.caption(
                    f"**Proposal ID:** `{prop.proposal_id}` | "
                    f"**Cryptographic Binding Hash (SHA-256):** `{prop.proposal_hash}` | "
                    f"**Approval State:** `{prop.approval_state}`"
                )

                if prop.rejection_reasons:
                    st.markdown("**Contracts Rejected & Specific Safeguard Triggers:**")
                    rej_rows = []
                    for mid, reasons in prop.rejection_reasons.items():
                        mc_obj = connector.get_market_candidate(mid)
                        rej_rows.append(
                            {
                                "Market ID": mid,
                                "Data Origin": mc_obj.data_origin if mc_obj else "unknown",
                                "Question": mc_obj.question if mc_obj else "Unknown",
                                "Location": mc_obj.location if mc_obj else "Unknown",
                                "Measurement": mc_obj.measurement if mc_obj else "Unknown",
                                "Rejection Reasons": " | ".join(reasons),
                            }
                        )
                    st.dataframe(pd.DataFrame(rej_rows), use_container_width=True)

            trace = last_res.get("tool_trace", [])
            st.subheader(f"Actual Tool Activity Log ({len(trace)} tool calls executed)")
            if trace:
                trace_summary = [
                    {
                        "Step": t["step"],
                        "Tool Name": t["tool"],
                        "Arguments": json.dumps(t["args"]),
                        "Elapsed (ms)": t.get("elapsed_ms", 0.0),
                        "Timestamp (UTC)": t["timestamp"],
                    }
                    for t in trace
                ]
                st.dataframe(pd.DataFrame(trace_summary), use_container_width=True)
                with st.expander("Inspect Full Structured Tool Outputs"):
                    st.json(trace)

    st.subheader("Polymarket Candidate Catalog (Authentic Cached / Live Snapshots)")
    catalog_rows = []
    for mc in list(connector._candidates_by_id.values())[:20]:
        yes_asks = mc.asks_by_outcome.get("Yes", [])
        best_ask = f"${yes_asks[0].price}" if yes_asks else "No active ask book"
        depth_shares = sum(float(lv.size) for lv in yes_asks)
        catalog_rows.append(
            {
                "Market ID": mc.market_id,
                "Origin Badge": mc.data_origin,
                "Status": mc.status,
                "Location": mc.location,
                "Measurement": mc.measurement,
                "Best Ask (Yes)": best_ask,
                "Ask Depth (Shares)": round(depth_shares, 1),
                "Retrieved At (UTC)": mc.retrieval_timestamp,
                "Question": mc.question,
                "Source URL": mc.source_url,
            }
        )
    st.dataframe(pd.DataFrame(catalog_rows), use_container_width=True)

    with st.expander("View Held-Out Agent Evaluation Report (12 Cases Across Strategies — Section 14)"):
        agent_eval = load_json_file(AGENT_EVAL_REPORT_PATH)
        if agent_eval:
            st.markdown(
                f"- **Total Held-Out Cases:** `{agent_eval['total_held_out_cases']}` | "
                f"**Correct Rejections:** `{agent_eval['correct_rejections']}` | "
                f"**Unsuitable Recommendations:** `{agent_eval['unsuitable_recommendations_made']}` | "
                f"**Budget/Approval Violations:** `{agent_eval['budget_and_approval_violations']}`"
            )
            st.dataframe(pd.DataFrame(agent_eval.get("cases", [])), use_container_width=True)


def render_view_d_approval_and_results() -> None:
    st.header("D. Human Approval, Scenario Outcomes & Paper Trading Audit Log")
    st.info(
        "**Human-Approved Paper Trading Only:** All positions are simulated records stored in local SQLite. "
        "No wallet credentials are requested and no real orders are ever submitted. "
        "Approvals bind cryptographically (`proposal_hash`) to the exact `proposal_id`, `market_id`, `outcome`, "
        "`paper_quantity`, `max_total_cost_gbp`, and `quote_timestamp`."
    )

    store = get_store()
    proposals = store.list_proposals(limit=20)

    if not proposals:
        st.write("No proposals saved yet. Run an assessment in **View C** to generate a proposal or rejection record.")
    else:
        st.subheader("1. Saved Assessment Proposals")
        prop_options = {
            f"{p.proposal_id} | {p.target_date} | {p.status} | Approval: {p.approval_state}": p
            for p in proposals
        }
        selected_label = st.selectbox("Select Proposal to Inspect or Approve/Reject:", list(prop_options.keys()))
        sel_prop = prop_options[selected_label]

        st.markdown(
            f"- **Proposal ID:** `{sel_prop.proposal_id}`\n"
            f"- **Binding Hash (SHA-256):** `{sel_prop.proposal_hash}`\n"
            f"- **Target Date:** `{sel_prop.target_date}` | **Budget:** `£{sel_prop.budget_gbp:.2f}`\n"
            f"- **Decision Status:** `{sel_prop.status}` | **Approval State:** `{sel_prop.approval_state}`\n"
            f"- **Data Origin:** `{sel_prop.data_origin or 'N/A'}` | **Quote Timestamp:** `{sel_prop.quote_timestamp or 'N/A'}`\n"
            f"- **Explanation:** {sel_prop.explanation}"
        )

        if sel_prop.calculation is not None:
            c = sel_prop.calculation
            st.subheader("2. Financial Calculations & Combined Scenario Outcome Comparison")
            st.caption(
                f"**FX Rate:** `1.00 GBP = {c.fx_rate_usd_per_gbp:.4f} USD` ({c.fx_rate_source}) | "
                f"**Fee Assumption:** `{c.fee_bps} bps` (`0.50%`) | "
                f"**Executable Paper Quantity:** `{c.executable_contracts} shares` @ avg ask `${c.average_ask_price_usd:.4f} USD` | "
                f"**Total Entry Cost:** `${c.total_entry_cost_usd:.2f} USD` (`£{c.total_entry_cost_gbp:.2f} GBP`)"
            )

            outcome_df = pd.DataFrame(
                [
                    {
                        "Scenario": "1. Adverse Weather Occurs & Contract Pays Out ($1.00/share)",
                        "Unhedged Pub Revenue (£)": f"£{c.adverse_weather_pub_revenue_gbp:,.2f}",
                        "Paper Hedge Net P&L (£)": f"£{c.net_profit_if_win_gbp:+,.2f}",
                        "Combined Pub + Hedge Outcome (£)": f"£{c.combined_outcome_if_adverse_and_contract_pays_gbp:,.2f}",
                        "Remaining Downside vs Reference (£)": f"£{c.remaining_downside_if_contract_pays_gbp:,.2f}",
                    },
                    {
                        "Scenario": "2. Adverse Weather Occurs, Contract Fails to Pay (Basis Risk)",
                        "Unhedged Pub Revenue (£)": f"£{c.adverse_weather_pub_revenue_gbp:,.2f}",
                        "Paper Hedge Net P&L (£)": f"£{c.net_loss_if_lose_gbp:+,.2f}",
                        "Combined Pub + Hedge Outcome (£)": f"£{c.combined_outcome_if_adverse_and_contract_fails_gbp:,.2f}",
                        "Remaining Downside vs Reference (£)": (
                            f"£{max(0.0, c.reference_weather_pub_revenue_gbp - c.combined_outcome_if_adverse_and_contract_fails_gbp):,.2f}"
                        ),
                    },
                    {
                        "Scenario": "3. Benign Reference Weather Occurs & Contract Expires ($0.00/share)",
                        "Unhedged Pub Revenue (£)": f"£{c.reference_weather_pub_revenue_gbp:,.2f}",
                        "Paper Hedge Net P&L (£)": f"£{c.net_loss_if_lose_gbp:+,.2f}",
                        "Combined Pub + Hedge Outcome (£)": f"£{c.combined_outcome_if_benign_and_contract_fails_gbp:,.2f}",
                        "Remaining Downside vs Reference (£)": f"£{abs(c.net_loss_if_lose_gbp):,.2f} (hedge cost)",
                    },
                ]
            )
            st.table(outcome_df)
            st.caption(
                "**Note:** Hypothetical scenario payouts above model a $1.00 USD/share resolution payout under the stated scenario "
                "and are distinct from actual historical or future market settlement."
            )

        if sel_prop.status == "recommend_paper_hedge":
            st.subheader("3. Human Oversight Controls (Approve or Reject Paper Position)")
            approver_note = st.text_input(
                "Reviewer / Approver Note:",
                value="Reviewed order-book depth, basis risk, and £ budget limit; approving simulated paper hedge.",
                key=f"note_{sel_prop.proposal_id}",
            )
            ac1, ac2, ac3 = st.columns(3)
            with ac1:
                if st.button("Approve & Record Simulated Paper Position", type="primary", use_container_width=True):
                    res = store.approve_proposal(
                        proposal_id=sel_prop.proposal_id,
                        confirmed_proposal_hash=sel_prop.proposal_hash,
                        confirmed_quantity=sel_prop.paper_quantity,
                        confirmed_max_cost_gbp=sel_prop.max_total_cost_gbp,
                        confirmed_quote_timestamp=sel_prop.quote_timestamp,
                        approver_note=approver_note,
                    )
                    if res.get("ok"):
                        st.success(
                            f"Approved! Recorded simulated paper position `{res['position_id']}` "
                            f"({res['paper_quantity']} shares, total cost £{res['total_entry_cost_gbp']:.2f})."
                        )
                    else:
                        st.error(res.get("error", "Approval failed."))
            with ac2:
                if st.button("Reject Proposal", use_container_width=True):
                    res = store.reject_proposal(sel_prop.proposal_id, reviewer_note=approver_note)
                    if res.get("ok"):
                        st.warning(f"Proposal `{sel_prop.proposal_id}` marked as rejected.")
                    else:
                        st.error(res.get("error", "Rejection failed."))
            with ac3:
                if st.button("Test Safeguard: Attempt Tampered Quantity Approval", use_container_width=True):
                    res = store.approve_proposal(
                        proposal_id=sel_prop.proposal_id,
                        confirmed_proposal_hash=sel_prop.proposal_hash,
                        confirmed_quantity=sel_prop.paper_quantity + 25,
                        confirmed_max_cost_gbp=sel_prop.max_total_cost_gbp,
                        confirmed_quote_timestamp=sel_prop.quote_timestamp,
                        approver_note="Tampered quantity test",
                    )
                    st.error(f"Safeguard Triggered: {res.get('error')}")

    st.subheader("4. Recorded Simulated Paper Positions (SQLite)")
    positions = store.get_paper_positions(limit=25)
    if positions:
        st.dataframe(pd.DataFrame(positions), use_container_width=True)
    else:
        st.caption("No simulated paper positions recorded yet.")

    st.subheader("5. Immutable Audit Log (Proposals, Approvals, Rejections & Blocked Violations)")
    audit_rows = store.get_audit_history(limit=40)
    if audit_rows:
        st.dataframe(pd.DataFrame(audit_rows), use_container_width=True)
    else:
        st.caption("No audit events logged yet.")


def main() -> None:
    include_test_fixtures, allow_live_refresh = render_header_and_disclosures()

    tab_a, tab_b, tab_c, tab_d = st.tabs(
        [
            "A. Data and Model",
            "B. Business Assessment",
            "C. Agent Assessment",
            "D. Approval and Results",
        ]
    )

    with tab_a:
        render_view_a_data_and_model()

    with tab_b:
        scenario_ctx = render_view_b_business_assessment()

    with tab_c:
        render_view_c_agent_assessment(
            scenario_ctx=scenario_ctx,
            include_test_fixtures=include_test_fixtures,
            allow_live_refresh=allow_live_refresh,
        )

    with tab_d:
        render_view_d_approval_and_results()


if __name__ == "__main__":
    main()
