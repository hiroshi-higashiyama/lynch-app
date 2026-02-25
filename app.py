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

        # Use Yahoo EPS as fallback for current EPS if EDINET not available
        eps_current = edinet["eps_current"]
        if eps_current is None and yahoo.get("eps_ttm") is not None:
            eps_current = yahoo["eps_ttm"]

        # Calculate indices
        results = calculate_lynch_indices(
            per=yahoo["per"],
            dividend_yield=yahoo["dividend_yield"],
            eps_current=eps_current,
            eps_previous=edinet["eps_previous"],
            eps_forecast=edinet["eps_forecast"],
            ordinary_income_current=edinet["ordinary_income_current"],
            ordinary_income_previous=edinet["ordinary_income_previous"],
            ordinary_income_two_years_ago=edinet["ordinary_income_two_years_ago"],
            ordinary_income_forecast=edinet["ordinary_income_forecast"],
        )

        response = {
            "stock_code": stock_code,
            "company_name": yahoo.get("company_name", "不明"),
            "stock_price": yahoo["stock_price"],
            "stock_price_fmt": f"¥{yahoo['stock_price']:,.0f}" if yahoo["stock_price"] else "N/A",
            "data_source_yahoo": "Yahoo Finance",
            "data_source_edinet": edinet.get("data_source", "EDINET"),
            **results,
        }

        return jsonify(response)

    except Exception:
        logger.exception("Error calculating Lynch index for %s", stock_code)
        return jsonify({"error": "計算中にエラーが発生しました。しばらくしてから再度お試しください。"}), 500


if __name__ == "__main__":
    app.run(debug=Config.DEBUG, host="0.0.0.0", port=5000)
