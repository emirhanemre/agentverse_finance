"""Deterministic financial calculations for Polymarket paper hedging of UK pub weather exposure.

All monetary calculations use `decimal.Decimal` with `ROUND_HALF_UP` and integer minor units
(pence for GBP, cents for USD).
Midpoint prices and historical price series are never treated as executable fills; entry cost
is computed strictly by walking the Level-2 ask order book ladder.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from typing import Any

from src.schemas import HedgeCalculationResult, MarketCandidate, OrderBookLevel

DEFAULT_FX_USD_PER_GBP = Decimal("1.2800")
DEFAULT_FX_SOURCE = (
    "Fixed paper simulation assumption (1.00 GBP = 1.2800 USD); not a live exchange rate"
)
DEFAULT_FEE_BPS = 50  # 0.50% simulated execution / spread-buffer fee in basis points


def _q2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def gbp_to_usd(amount_gbp: Decimal, fx_usd_per_gbp: Decimal = DEFAULT_FX_USD_PER_GBP) -> Decimal:
    if fx_usd_per_gbp <= Decimal("0"):
        raise ValueError("FX rate (USD per GBP) must be strictly positive.")
    return _q2(amount_gbp * fx_usd_per_gbp)


def usd_to_gbp(amount_usd: Decimal, fx_usd_per_gbp: Decimal = DEFAULT_FX_USD_PER_GBP) -> Decimal:
    if fx_usd_per_gbp <= Decimal("0"):
        raise ValueError("FX rate (USD per GBP) must be strictly positive.")
    return _q2(amount_usd / fx_usd_per_gbp)


def walk_ask_book_for_budget(
    asks: list[OrderBookLevel],
    max_total_spend_usd: Decimal,
    fee_bps: int = DEFAULT_FEE_BPS,
    target_payout_usd: Decimal | None = None,
) -> dict[str, Any]:
    """Walk the sorted ask ladder to buy integer outcome shares within budget and optional target payout.

    Each outcome share on Polymarket pays $1.00 USD upon a winning resolution and $0.00 USD otherwise.
    We size integer shares (`executable_contracts`) so that:
    1) Total entry cost including fees (`gross_cost * (1 + fee_bps/10000)`) <= `max_total_spend_usd`, AND
    2) If `target_payout_usd` is specified (e.g. to offset estimated downside without over-betting),
       net hedge profit on a winning payout does not exceed the target downside offset unless constrained by lot integer rounding.
    """
    if max_total_spend_usd <= Decimal("0") or not asks:
        return {
            "executable_contracts": 0,
            "average_ask_price_usd": Decimal("0.0000"),
            "gross_entry_cost_usd": Decimal("0.00"),
            "estimated_fee_usd": Decimal("0.00"),
            "total_entry_cost_usd": Decimal("0.00"),
            "depth_exhausted": True,
        }

    fee_multiplier = Decimal("1") + (Decimal(str(fee_bps)) / Decimal("10000"))
    max_gross_usd = max_total_spend_usd / fee_multiplier

    sorted_asks = sorted(asks, key=lambda lv: lv.price)
    remaining_gross_usd = max_gross_usd
    remaining_target_net_usd = target_payout_usd if (target_payout_usd and target_payout_usd > Decimal("0")) else None

    total_shares = 0
    gross_cost = Decimal("0.0000")
    exhausted_all_levels = True

    for level in sorted_asks:
        price = level.price
        avail_shares = int(level.size.to_integral_value(rounding=ROUND_FLOOR))
        if avail_shares <= 0 or price <= Decimal("0") or price >= Decimal("1"):
            continue

        affordable_at_level = int((remaining_gross_usd / price).to_integral_value(rounding=ROUND_FLOOR))
        if affordable_at_level <= 0:
            exhausted_all_levels = False
            break

        needed_at_level = avail_shares
        if remaining_target_net_usd is not None:
            # Each share costs `price * fee_multiplier` and pays $1.00, so net gain per share is `1 - price * fee_multiplier`
            net_gain_per_share = Decimal("1.0000") - (price * fee_multiplier)
            if net_gain_per_share <= Decimal("0"):
                exhausted_all_levels = False
                break
            needed_for_downside = int(
                (remaining_target_net_usd / net_gain_per_share).to_integral_value(rounding=ROUND_HALF_UP)
            )
            needed_at_level = min(avail_shares, max(0, needed_for_downside))

        take_shares = min(avail_shares, affordable_at_level, needed_at_level)
        if take_shares < avail_shares:
            exhausted_all_levels = False

        if take_shares > 0:
            cost_chunk = Decimal(take_shares) * price
            total_shares += take_shares
            gross_cost += cost_chunk
            remaining_gross_usd -= cost_chunk
            if remaining_target_net_usd is not None:
                net_gain_per_share = Decimal("1.0000") - (price * fee_multiplier)
                remaining_target_net_usd = max(
                    Decimal("0"), remaining_target_net_usd - (Decimal(take_shares) * net_gain_per_share)
                )

        if remaining_gross_usd <= Decimal("0.01") or (
            remaining_target_net_usd is not None and remaining_target_net_usd <= Decimal("0.50")
        ):
            break

    if total_shares == 0:
        return {
            "executable_contracts": 0,
            "average_ask_price_usd": Decimal("0.0000"),
            "gross_entry_cost_usd": Decimal("0.00"),
            "estimated_fee_usd": Decimal("0.00"),
            "total_entry_cost_usd": Decimal("0.00"),
            "depth_exhausted": exhausted_all_levels,
        }

    gross_rounded = _q2(gross_cost)
    fee_usd = _q2(gross_rounded * (Decimal(str(fee_bps)) / Decimal("10000")))
    total_cost_usd = _q2(gross_rounded + fee_usd)

    # Strict budget guard: if rounding pushed total_cost_usd 1 cent above max_total_spend_usd, trim 1 share
    while total_shares > 0 and total_cost_usd > max_total_spend_usd:
        avg_p = gross_cost / Decimal(total_shares)
        total_shares -= 1
        gross_cost = avg_p * Decimal(total_shares)
        gross_rounded = _q2(gross_cost)
        fee_usd = _q2(gross_rounded * (Decimal(str(fee_bps)) / Decimal("10000")))
        total_cost_usd = _q2(gross_rounded + fee_usd)

    avg_ask = _q4(gross_cost / Decimal(total_shares)) if total_shares > 0 else Decimal("0.0000")
    return {
        "executable_contracts": total_shares,
        "average_ask_price_usd": avg_ask,
        "gross_entry_cost_usd": gross_rounded,
        "estimated_fee_usd": fee_usd,
        "total_entry_cost_usd": total_cost_usd,
        "depth_exhausted": exhausted_all_levels,
    }


def evaluate_candidate_hedge(
    market: MarketCandidate,
    outcome_selected: str,
    target_date: str,
    budget_gbp: float,
    adverse_weather_pub_revenue_gbp: float,
    reference_weather_pub_revenue_gbp: float,
    fx_rate_usd_per_gbp: float = float(DEFAULT_FX_USD_PER_GBP),
    fx_rate_source: str = DEFAULT_FX_SOURCE,
    fee_bps: int = DEFAULT_FEE_BPS,
    cap_to_downside: bool = True,
) -> HedgeCalculationResult:
    """Compute exact paper hedge entry cost, payout, net P&L, and combined business + hedge scenario outcomes."""
    budget_dec_gbp = _q2(Decimal(str(budget_gbp)))
    fx_dec = _q4(Decimal(str(fx_rate_usd_per_gbp)))
    budget_dec_usd = gbp_to_usd(budget_dec_gbp, fx_dec)

    adv_rev_gbp = _q2(Decimal(str(adverse_weather_pub_revenue_gbp)))
    ref_rev_gbp = _q2(Decimal(str(reference_weather_pub_revenue_gbp)))
    unhedged_downside_gbp = max(Decimal("0.00"), ref_rev_gbp - adv_rev_gbp)
    target_downside_usd = gbp_to_usd(unhedged_downside_gbp, fx_dec) if cap_to_downside else None

    asks = market.asks_by_outcome.get(outcome_selected, [])
    fill = walk_ask_book_for_budget(
        asks=asks,
        max_total_spend_usd=budget_dec_usd,
        fee_bps=fee_bps,
        target_payout_usd=target_downside_usd,
    )

    qty = int(fill["executable_contracts"])
    total_cost_usd: Decimal = fill["total_entry_cost_usd"]
    total_cost_gbp = usd_to_gbp(total_cost_usd, fx_dec)
    # Ensure rounding in USD->GBP conversion never exceeds budget_dec_gbp when USD was within budget
    if total_cost_gbp > budget_dec_gbp and total_cost_usd <= budget_dec_usd:
        total_cost_gbp = budget_dec_gbp

    unfilled_budget_gbp = max(Decimal("0.00"), _q2(budget_dec_gbp - total_cost_gbp))

    payout_win_usd = _q2(Decimal(qty) * Decimal("1.00"))
    payout_win_gbp = usd_to_gbp(payout_win_usd, fx_dec)
    net_profit_win_gbp = _q2(payout_win_gbp - total_cost_gbp)
    net_loss_lose_gbp = _q2(-total_cost_gbp)

    # Combined pub revenue + paper hedge outcome under explicitly stated scenarios:
    # 1. Adverse weather occurs AND the Polymarket contract resolves in our favour (pays $1/share)
    combined_adverse_and_pays_gbp = _q2(adv_rev_gbp + net_profit_win_gbp)
    # 2. Adverse weather occurs AT THE PUB, but the contract fails to pay (basis risk: e.g. wrong station/metric)
    combined_adverse_and_fails_gbp = _q2(adv_rev_gbp + net_loss_lose_gbp)
    # 3. Benign reference weather occurs at the pub AND the adverse weather contract expires worthless
    combined_benign_and_fails_gbp = _q2(ref_rev_gbp + net_loss_lose_gbp)

    remaining_downside_if_pays_gbp = max(
        Decimal("0.00"), _q2(ref_rev_gbp - combined_adverse_and_pays_gbp)
    )

    basis_note = (
        f"Contract resolves on '{market.measurement}' at '{market.location}' via {market.resolution_source}. "
        f"If the pub suffers adverse weather (£{adv_rev_gbp} vs £{ref_rev_gbp} reference) AND the contract pays out, "
        f"remaining downside is reduced from £{unhedged_downside_gbp} to £{remaining_downside_if_pays_gbp}. "
        f"However, if the pub loses revenue while the contract does not trigger (basis mismatch), "
        f"combined revenue + hedge outcome worsens to £{combined_adverse_and_fails_gbp}."
    )

    return HedgeCalculationResult(
        market_id=market.market_id,
        outcome_selected=outcome_selected,
        target_date=target_date,
        budget_gbp=float(budget_dec_gbp),
        budget_pence=int((budget_dec_gbp * 100).to_integral_value(rounding=ROUND_HALF_UP)),
        fx_rate_usd_per_gbp=float(fx_dec),
        fx_rate_source=fx_rate_source,
        fee_bps=fee_bps,
        executable_contracts=qty,
        average_ask_price_usd=float(fill["average_ask_price_usd"]),
        gross_entry_cost_usd=float(fill["gross_entry_cost_usd"]),
        estimated_fee_usd=float(fill["estimated_fee_usd"]),
        total_entry_cost_usd=float(total_cost_usd),
        total_entry_cost_gbp=float(total_cost_gbp),
        total_entry_cost_pence=int((total_cost_gbp * 100).to_integral_value(rounding=ROUND_HALF_UP)),
        unfilled_budget_gbp=float(unfilled_budget_gbp),
        depth_exhausted=bool(fill["depth_exhausted"]),
        payout_if_win_usd=float(payout_win_usd),
        payout_if_win_gbp=float(payout_win_gbp),
        net_profit_if_win_gbp=float(net_profit_win_gbp),
        net_loss_if_lose_gbp=float(net_loss_lose_gbp),
        adverse_weather_pub_revenue_gbp=float(adv_rev_gbp),
        reference_weather_pub_revenue_gbp=float(ref_rev_gbp),
        estimated_unhedged_downside_gbp=float(unhedged_downside_gbp),
        combined_outcome_if_adverse_and_contract_pays_gbp=float(combined_adverse_and_pays_gbp),
        combined_outcome_if_adverse_and_contract_fails_gbp=float(combined_adverse_and_fails_gbp),
        combined_outcome_if_benign_and_contract_fails_gbp=float(combined_benign_and_fails_gbp),
        remaining_downside_if_contract_pays_gbp=float(remaining_downside_if_pays_gbp),
        basis_risk_summary=basis_note,
    )
