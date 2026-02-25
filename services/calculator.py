"""Peter Lynch Index calculator."""


def _safe_div(numerator: float, denominator: float) -> float | None:
    """Safe division returning None if denominator is zero or None."""
    if denominator is None or denominator == 0:
        return None
    if numerator is None:
        return None
    return numerator / denominator


def _growth_rate(current: float | None, previous: float | None) -> float | None:
    """Calculate growth rate as percentage: (current - previous) / previous * 100."""
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous) * 100


def _avg_growth_rate(
    current: float | None,
    previous: float | None,
    two_years_ago: float | None,
) -> float | None:
    """Calculate average growth rate over two periods.

    avg = [((prev / two_ago) * 100 - 100) + ((current / prev) * 100 - 100)] / 2
    """
    if any(v is None for v in (current, previous, two_years_ago)):
        return None
    if previous == 0 or two_years_ago == 0:
        return None
    g1 = (previous / abs(two_years_ago)) * 100 - 100
    g2 = (current / abs(previous)) * 100 - 100
    return (g1 + g2) / 2


def _lynch_index(growth_rate: float | None, dividend_yield: float | None, per: float | None) -> float | None:
    """Calculate Peter Lynch index: (growth_rate + dividend_yield) / PER."""
    if growth_rate is None or dividend_yield is None or per is None or per == 0:
        return None
    return (growth_rate + dividend_yield) / per


def _evaluate(index_value: float | None) -> str:
    """Evaluate the Lynch index value."""
    if index_value is None:
        return "算出不可"
    if index_value >= 2.0:
        return "投資対象"
    if index_value >= 1.5:
        return "まずまず"
    if index_value >= 1.0:
        return "見込み薄"
    return "見込み薄"


def _evaluation_class(label: str) -> str:
    """Return CSS class for evaluation label."""
    if label == "投資対象":
        return "eval-good"
    if label == "まずまず":
        return "eval-fair"
    if label == "見込み薄":
        return "eval-poor"
    return "eval-na"


def calculate_lynch_indices(
    per: float | None,
    dividend_yield: float | None,
    eps_current: float | None,
    eps_previous: float | None,
    eps_forecast: float | None,
    ordinary_income_current: float | None,
    ordinary_income_previous: float | None,
    ordinary_income_two_years_ago: float | None,
    ordinary_income_forecast: float | None,
) -> dict:
    """Calculate all four Peter Lynch indices and return detailed results.

    Returns a dict with:
        - indices: list of 4 index results
        - input_data: summary of input data
        - growth_rates: intermediate growth rate values
    """
    # Growth rates
    eps_growth_current = _growth_rate(eps_current, eps_previous)
    eps_growth_forecast = _growth_rate(eps_forecast, eps_previous)
    oi_avg_growth_current = _avg_growth_rate(
        ordinary_income_current, ordinary_income_previous, ordinary_income_two_years_ago
    )
    oi_avg_growth_forecast = _avg_growth_rate(
        ordinary_income_forecast, ordinary_income_previous, ordinary_income_two_years_ago
    )

    # Lynch indices
    idx_eps_current = _lynch_index(eps_growth_current, dividend_yield, per)
    idx_eps_forecast = _lynch_index(eps_growth_forecast, dividend_yield, per)
    idx_oi_current = _lynch_index(oi_avg_growth_current, dividend_yield, per)
    idx_oi_forecast = _lynch_index(oi_avg_growth_forecast, dividend_yield, per)

    def _fmt(v, decimals=2):
        if v is None:
            return "N/A"
        return f"{v:,.{decimals}f}"

    def _fmt_int(v):
        if v is None:
            return "N/A"
        return f"{v:,.0f}"

    indices = [
        {
            "name": "当期実績EPSベース",
            "growth_rate": eps_growth_current,
            "growth_rate_fmt": _fmt(eps_growth_current),
            "index_value": idx_eps_current,
            "index_value_fmt": _fmt(idx_eps_current),
            "evaluation": _evaluate(idx_eps_current),
            "evaluation_class": _evaluation_class(_evaluate(idx_eps_current)),
            "formula": f"({_fmt(eps_growth_current)}% + {_fmt(dividend_yield)}%) ÷ {_fmt(per)} = {_fmt(idx_eps_current)}",
            "growth_formula": f"({_fmt(eps_current)} − {_fmt(eps_previous)}) ÷ |{_fmt(eps_previous)}| × 100 = {_fmt(eps_growth_current)}%",
        },
        {
            "name": "来期予想EPSベース",
            "growth_rate": eps_growth_forecast,
            "growth_rate_fmt": _fmt(eps_growth_forecast),
            "index_value": idx_eps_forecast,
            "index_value_fmt": _fmt(idx_eps_forecast),
            "evaluation": _evaluate(idx_eps_forecast),
            "evaluation_class": _evaluation_class(_evaluate(idx_eps_forecast)),
            "formula": f"({_fmt(eps_growth_forecast)}% + {_fmt(dividend_yield)}%) ÷ {_fmt(per)} = {_fmt(idx_eps_forecast)}",
            "growth_formula": f"({_fmt(eps_forecast)} − {_fmt(eps_previous)}) ÷ |{_fmt(eps_previous)}| × 100 = {_fmt(eps_growth_forecast)}%",
        },
        {
            "name": "当期実績経常利益ベース",
            "growth_rate": oi_avg_growth_current,
            "growth_rate_fmt": _fmt(oi_avg_growth_current),
            "index_value": idx_oi_current,
            "index_value_fmt": _fmt(idx_oi_current),
            "evaluation": _evaluate(idx_oi_current),
            "evaluation_class": _evaluation_class(_evaluate(idx_oi_current)),
            "formula": f"({_fmt(oi_avg_growth_current)}% + {_fmt(dividend_yield)}%) ÷ {_fmt(per)} = {_fmt(idx_oi_current)}",
            "growth_formula": (
                f"[({_fmt_int(ordinary_income_previous)} ÷ {_fmt_int(ordinary_income_two_years_ago)} × 100 − 100) + "
                f"({_fmt_int(ordinary_income_current)} ÷ {_fmt_int(ordinary_income_previous)} × 100 − 100)] ÷ 2 = {_fmt(oi_avg_growth_current)}%"
            ),
        },
        {
            "name": "来期予想経常利益ベース",
            "growth_rate": oi_avg_growth_forecast,
            "growth_rate_fmt": _fmt(oi_avg_growth_forecast),
            "index_value": idx_oi_forecast,
            "index_value_fmt": _fmt(idx_oi_forecast),
            "evaluation": _evaluate(idx_oi_forecast),
            "evaluation_class": _evaluation_class(_evaluate(idx_oi_forecast)),
            "formula": f"({_fmt(oi_avg_growth_forecast)}% + {_fmt(dividend_yield)}%) ÷ {_fmt(per)} = {_fmt(idx_oi_forecast)}",
            "growth_formula": (
                f"[({_fmt_int(ordinary_income_previous)} ÷ {_fmt_int(ordinary_income_two_years_ago)} × 100 − 100) + "
                f"({_fmt_int(ordinary_income_forecast)} ÷ {_fmt_int(ordinary_income_previous)} × 100 − 100)] ÷ 2 = {_fmt(oi_avg_growth_forecast)}%"
            ),
        },
    ]

    input_data = {
        "per": _fmt(per),
        "dividend_yield": _fmt(dividend_yield),
        "eps_current": _fmt(eps_current),
        "eps_previous": _fmt(eps_previous),
        "eps_forecast": _fmt(eps_forecast),
        "ordinary_income_current": _fmt_int(ordinary_income_current),
        "ordinary_income_previous": _fmt_int(ordinary_income_previous),
        "ordinary_income_two_years_ago": _fmt_int(ordinary_income_two_years_ago),
        "ordinary_income_forecast": _fmt_int(ordinary_income_forecast),
    }

    return {
        "indices": indices,
        "input_data": input_data,
    }
