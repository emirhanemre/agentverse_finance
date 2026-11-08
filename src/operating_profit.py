"""Illustrative operating profit from model revenue and explicit cost assumptions.

This is an arithmetic scenario, not a new regression, actual accounts or a
cashflow forecast. Expense assumptions are held fixed across weather scenarios.
"""
from decimal import Decimal, ROUND_HALF_UP

from src.api_schemas import OperatingCostsInput, OperatingProfitResponse


def estimate_operating_profit(comparison, costs):
    costs = OperatingCostsInput.model_validate(costs)
    fixed = Decimal(str(costs.fixed_daily_cost_gbp))
    rate = Decimal(str(costs.variable_cost_pct)) / 100

    def money(value):
        return Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

    def profit(revenue):
        revenue = money(revenue)
        return revenue - money(revenue * rate) - fixed

    def scenario(revenue, prediction):
        revenue = money(revenue)
        variable = money(revenue * rate)
        result = profit(revenue)
        low = prediction.get('prediction_interval_80_low_gbp')
        high = prediction.get('prediction_interval_80_high_gbp')
        return {
            'revenue_gbp': float(revenue),
            'variable_cost_gbp': float(variable),
            'fixed_cost_gbp': float(fixed),
            'total_cost_gbp': float(variable + fixed),
            'operating_profit_gbp': float(result),
            'operating_margin_pct': float(money(result / revenue * 100)) if revenue else None,
            'prediction_interval_80_low_gbp': float(profit(low)) if low is not None else None,
            'prediction_interval_80_high_gbp': float(profit(high)) if high is not None else None,
        }

    selected = scenario(comparison['scenario_predicted_revenue_gbp'], comparison.get('scenario_prediction', {}))
    reference = scenario(comparison['reference_predicted_revenue_gbp'], comparison.get('reference_prediction', {}))
    return OperatingProfitResponse(
        target_date=comparison['date'],
        origin='demo_cost_assumptions', assumptions=costs,
        selected=selected, reference=reference,
        profit_difference_gbp=float(money(Decimal(str(selected['operating_profit_gbp'])) - Decimal(str(reference['operating_profit_gbp'])))),
        note='Estimated revenue minus assumed variable costs and fixed daily costs. Costs are editable demo assumptions, not imported expenses. Before tax/financing; excludes paper hedges and payment timing. Revenue-model intervals hold cost assumptions fixed and do not include expense uncertainty. This is not a cashflow forecast.',
    ).model_dump(mode='json')
