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
        yahoo_used_for_eps = False
        yahoo_used_for_oi = False

        # Fallback: use Yahoo Finance data when EDINET data is missing
        yearly = yahoo.get("yearly_earnings", [])

        if eps_current is None and yahoo.get("eps_ttm") is not None:
            eps_current = yahoo["eps_ttm"]
            yahoo_used_for_eps = True

        if eps_previous is None and yahoo.get("eps_ttm") is not None and yahoo.get("earnings_growth") is not None:
            # Derive previous EPS from trailing EPS and growth rate
            growth = yahoo["earnings_growth"] / 100
            if growth != -1:
                eps_previous = yahoo["eps_ttm"] / (1 + growth)
                yahoo_used_for_eps = True

        if eps_forecast is None and yahoo.get("forward_eps") is not None:
            eps_forecast = yahoo["forward_eps"]
            yahoo_used_for_eps = True

        if oi_current is None and len(yearly) >= 1:
            oi_current = yearly[0]["earnings"]
            yahoo_used_for_oi = True
        if oi_previous is None and len(yearly) >= 2:
            oi_previous = yearly[1]["earnings"]
            yahoo_used_for_oi = True
        if oi_two_years_ago is None and len(yearly) >= 3:
            oi_two_years_ago = yearly[2]["earnings"]
            yahoo_used_for_oi = True

        if yahoo_used_for_eps or yahoo_used_for_oi:
            edinet_source = "Yahoo Finance (EDINET未設定のため代替)"

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


if __name__ == "__main__":
    app.run(debug=Config.DEBUG, host="0.0.0.0", port=5000)
