"""Flask application for the Peter Lynch Index Calculator."""

import logging
import re

from flask import Flask, jsonify, render_template, request

from config import Config
from services.calculator import calculate_lynch_indices
from services.edinet import fetch_edinet_data
from services.yahoo_finance import fetch_yahoo_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Simple in-memory cache: {stock_code: {data: ..., timestamp: ...}}
_cache: dict = {}


def _validate_stock_code(code: str) -> str | None:
    """Validate and normalize a Japanese stock code. Returns None if invalid."""
    code = code.strip()
    if re.fullmatch(r"\d{4}", code):
        return code
    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    """API endpoint to calculate Peter Lynch indices for a stock."""
    data = request.get_json(silent=True) or {}
    raw_code = data.get("stock_code", "")
    stock_code = _validate_stock_code(raw_code)

    if stock_code is None:
        return jsonify({"error": "有効な4桁の証券コードを入力してください。"}), 400

    try:
        # Fetch data from Yahoo Finance
        yahoo = fetch_yahoo_data(stock_code)

        if yahoo["stock_price"] is None and yahoo["per"] is None:
            return jsonify({
                "error": f"証券コード {stock_code} のデータを取得できませんでした。コードを確認してください。"
            }), 404

        # Fetch data from EDINET
        edinet = fetch_edinet_data(stock_code)

        # Build input values, using Yahoo as fallback when EDINET is unavailable
        eps_current = edinet["eps_current"]
        eps_previous = edinet["eps_previous"]
        eps_forecast = edinet["eps_forecast"]
        oi_current = edinet["ordinary_income_current"]
        oi_previous = edinet["ordinary_income_previous"]
        oi_two_years_ago = edinet["ordinary_income_two_years_ago"]
        oi_forecast = edinet["ordinary_income_forecast"]

        edinet_source = edinet.get("data_source", "EDINET")
        yahoo_fallback_used = False

        # --- Fallback: use Yahoo Finance data when EDINET data is missing ---
        yearly_earn = yahoo.get("yearly_earnings", [])
        yearly_ni = yahoo.get("yearly_net_income", [])

        # Strategy 1: EPS from Yahoo trailingEps / forwardEps
        if eps_current is None and yahoo.get("eps_ttm") is not None:
            eps_current = yahoo["eps_ttm"]
            yahoo_fallback_used = True

        if eps_forecast is None and yahoo.get("forward_eps") is not None:
            eps_forecast = yahoo["forward_eps"]
            yahoo_fallback_used = True

        # Strategy 2: eps_previous from earnings_growth
        if eps_previous is None and eps_current is not None and yahoo.get("earnings_growth") is not None:
            growth = yahoo["earnings_growth"] / 100
            if growth != -1:
                eps_previous = round(eps_current / (1 + growth), 2)
                yahoo_fallback_used = True

        # Strategy 3: eps_previous from yearly net income + PER-derived shares
        if eps_previous is None and eps_current is not None and len(yearly_ni) >= 2:
            # Estimate shares outstanding from latest net income / EPS
            latest_ni = yearly_ni[0]["net_income"]
            if latest_ni and eps_current and eps_current != 0:
                est_shares = latest_ni / eps_current
                if est_shares > 0:
                    prev_ni = yearly_ni[1]["net_income"]
                    eps_previous = round(prev_ni / est_shares, 2)
                    yahoo_fallback_used = True

        # Strategy 4: ordinary income from incomeStatementHistory (most reliable)
        if not oi_current and len(yearly_ni) >= 1:
            oi_current = yearly_ni[0]["net_income"]
            yahoo_fallback_used = True
        if not oi_previous and len(yearly_ni) >= 2:
            oi_previous = yearly_ni[1]["net_income"]
            yahoo_fallback_used = True
        if not oi_two_years_ago and len(yearly_ni) >= 3:
            oi_two_years_ago = yearly_ni[2]["net_income"]
            yahoo_fallback_used = True

        # Strategy 5: ordinary income from yearly_earnings (financialsChart) fallback
        if not oi_current and len(yearly_earn) >= 1 and yearly_earn[0]["earnings"]:
            oi_current = yearly_earn[0]["earnings"]
            yahoo_fallback_used = True
        if not oi_previous and len(yearly_earn) >= 2 and yearly_earn[1]["earnings"]:
            oi_previous = yearly_earn[1]["earnings"]
            yahoo_fallback_used = True
        if not oi_two_years_ago and len(yearly_earn) >= 3 and yearly_earn[2]["earnings"]:
            oi_two_years_ago = yearly_earn[2]["earnings"]
            yahoo_fallback_used = True

        if yahoo_fallback_used:
            edinet_source = "Yahoo Finance (EDINET未設定のため代替)"

        logger.info(
            "Calc input for %s: eps_c=%s, eps_p=%s, eps_f=%s, "
            "oi_c=%s, oi_p=%s, oi_2y=%s, per=%s, dy=%s",
            stock_code, eps_current, eps_previous, eps_forecast,
            oi_current, oi_previous, oi_two_years_ago,
            yahoo["per"], yahoo["dividend_yield"],
        )

        # Calculate indices
        results = calculate_lynch_indices(
            per=yahoo["per"],
            dividend_yield=yahoo["dividend_yield"],
            eps_current=eps_current,
            eps_previous=eps_previous,
            eps_forecast=eps_forecast,
            ordinary_income_current=oi_current,
            ordinary_income_previous=oi_previous,
            ordinary_income_two_years_ago=oi_two_years_ago,
            ordinary_income_forecast=oi_forecast,
        )

        response = {
            "stock_code": stock_code,
            "company_name": yahoo.get("company_name", "不明"),
            "stock_price": yahoo["stock_price"],
            "stock_price_fmt": f"¥{yahoo['stock_price']:,.0f}" if yahoo["stock_price"] else "N/A",
            "data_source_yahoo": "Yahoo Finance",
            "data_source_edinet": edinet_source,
            **results,
        }

        return jsonify(response)

    except Exception:
        logger.exception("Error calculating Lynch index for %s", stock_code)
        return jsonify({"error": "計算中にエラーが発生しました。しばらくしてから再度お試しください。"}), 500


@app.route("/api/debug/<stock_code>")
def api_debug(stock_code):
    """Debug endpoint: show raw Yahoo Finance data (dev only)."""
    code = _validate_stock_code(stock_code)
    if code is None:
        return jsonify({"error": "invalid code"}), 400
    yahoo = fetch_yahoo_data(code)
    return jsonify(yahoo)


if __name__ == "__main__":
    app.run(debug=Config.DEBUG, host="0.0.0.0", port=5000)
