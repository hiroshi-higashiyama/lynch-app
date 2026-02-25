"""Yahoo Finance data fetcher for Japanese stocks using direct API calls."""

import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

YAHOO_FINANCE_QUERY_URL = (
    "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
)


def fetch_yahoo_data(stock_code: str) -> dict:
    """Fetch PER, dividend yield, and stock price from Yahoo Finance.

    Tries the Yahoo Finance quoteSummary API first, falls back to scraping
    the Japanese Yahoo Finance site.

    Args:
        stock_code: 4-digit Japanese stock code (e.g. "7203").

    Returns:
        Dict with keys: stock_price, per, dividend_yield, company_name, eps_ttm.
        Values are None when unavailable.
    """
    ticker_symbol = f"{stock_code}.T"
    result = {
        "stock_price": None,
        "per": None,
        "dividend_yield": None,
        "company_name": None,
        "eps_ttm": None,
    }

    try:
        url = YAHOO_FINANCE_QUERY_URL.format(ticker=ticker_symbol)
        params = {
            "modules": "price,summaryDetail,defaultKeyStatistics,earnings",
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            ),
        }

        resp = requests.get(url, params=params, headers=headers, timeout=15)

        if resp.status_code != 200:
            logger.warning(
                "Yahoo Finance API returned %d for %s",
                resp.status_code,
                ticker_symbol,
            )
            return _fallback_scrape(stock_code, result)

        data = resp.json()
        quote_summary = data.get("quoteSummary", {}).get("result", [])
        if not quote_summary:
            return _fallback_scrape(stock_code, result)

        info = quote_summary[0]

        # Price module
        price_data = info.get("price", {})
        result["company_name"] = price_data.get("longName") or price_data.get(
            "shortName"
        )
        result["stock_price"] = _extract_raw(
            price_data.get("regularMarketPrice")
        )

        # Summary detail module
        summary = info.get("summaryDetail", {})
        result["per"] = _extract_raw(summary.get("trailingPE"))
        if result["per"] is None:
            result["per"] = _extract_raw(summary.get("forwardPE"))

        raw_yield = _extract_raw(summary.get("dividendYield"))
        if raw_yield is not None:
            result["dividend_yield"] = round(raw_yield * 100, 2)
        else:
            result["dividend_yield"] = 0.0

        # Default key statistics for EPS
        stats = info.get("defaultKeyStatistics", {})
        result["eps_ttm"] = _extract_raw(stats.get("trailingEps"))

    except Exception:
        logger.exception(
            "Failed to fetch Yahoo Finance data for %s", ticker_symbol
        )
        return _fallback_scrape(stock_code, result)

    return result


def _extract_raw(field) -> float | None:
    """Extract raw value from Yahoo Finance API field."""
    if field is None:
        return None
    if isinstance(field, dict):
        return field.get("raw")
    if isinstance(field, (int, float)):
        return float(field)
    return None


def _fallback_scrape(stock_code: str, result: dict) -> dict:
    """Fallback: scrape Yahoo Finance Japan website for basic data."""
    try:
        url = f"https://finance.yahoo.co.jp/quote/{stock_code}.T"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            ),
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return result

        soup = BeautifulSoup(resp.text, "lxml")

        # Company name from title
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text()
            if "】" in title_text:
                name_part = title_text.split("】")[1].split("の")[0].strip()
                if name_part:
                    result["company_name"] = name_part

        # Extract detail values
        detail_items = soup.select("li")
        for item in detail_items:
            text = item.get_text()
            if "PER" in text and "倍" in text:
                try:
                    per_val = (
                        text.split("PER")[1]
                        .replace("倍", "")
                        .replace("(", "")
                        .replace(")", "")
                        .strip()
                        .replace(",", "")
                    )
                    result["per"] = float(per_val)
                except (ValueError, IndexError):
                    pass
            if "配当利回り" in text and "%" in text:
                try:
                    dy_val = (
                        text.split("配当利回り")[1]
                        .replace("%", "")
                        .replace("(", "")
                        .replace(")", "")
                        .strip()
                    )
                    result["dividend_yield"] = float(dy_val)
                except (ValueError, IndexError):
                    pass

    except Exception:
        logger.exception("Fallback scrape failed for %s", stock_code)

    return result
