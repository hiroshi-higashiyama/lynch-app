"""Yahoo Finance data fetcher for Japanese stocks using crumb-based authentication."""

import logging
import threading

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

YAHOO_FINANCE_QUERY_URL = (
    "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
)

# Module-level session cache for crumb authentication
_session_lock = threading.Lock()
_cached_session: requests.Session | None = None
_cached_crumb: str | None = None


def _get_authenticated_session() -> tuple[requests.Session, str]:
    """Get an authenticated Yahoo Finance session with a valid crumb.

    Yahoo Finance API requires a crumb token + session cookies for authentication.
    This function fetches the cookies and crumb, caching them for reuse.
    """
    global _cached_session, _cached_crumb

    with _session_lock:
        if _cached_session is not None and _cached_crumb is not None:
            return _cached_session, _cached_crumb

        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

        # Step 1: Visit fc.yahoo.com to get initial cookies
        try:
            session.get("https://fc.yahoo.com/", timeout=10, allow_redirects=True)
        except requests.RequestException:
            pass  # Cookie may still be set even on error

        # Step 2: Get crumb using the session cookies
        crumb_url = "https://query2.finance.yahoo.com/v1/test/getcrumb"
        resp = session.get(crumb_url, timeout=10)
        resp.raise_for_status()
        crumb = resp.text.strip()

        if not crumb:
            raise ValueError("Failed to obtain Yahoo Finance crumb token")

        _cached_session = session
        _cached_crumb = crumb
        logger.info("Yahoo Finance crumb authentication successful")
        return session, crumb


def _invalidate_session():
    """Invalidate the cached session so the next call re-authenticates."""
    global _cached_session, _cached_crumb
    with _session_lock:
        _cached_session = None
        _cached_crumb = None


def fetch_yahoo_data(stock_code: str) -> dict:
    """Fetch PER, dividend yield, and stock price from Yahoo Finance.

    Uses crumb-based authentication for the Yahoo Finance API.
    Falls back to scraping the Japanese Yahoo Finance site on failure.

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

    for attempt in range(2):
        try:
            session, crumb = _get_authenticated_session()

            url = YAHOO_FINANCE_QUERY_URL.format(ticker=ticker_symbol)
            params = {
                "modules": "price,summaryDetail,defaultKeyStatistics,earnings",
                "crumb": crumb,
            }

            resp = session.get(url, params=params, timeout=15)

            if resp.status_code == 401 and attempt == 0:
                # Crumb expired — invalidate and retry
                logger.info("Crumb expired, re-authenticating...")
                _invalidate_session()
                continue

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

            return result

        except Exception:
            if attempt == 0:
                _invalidate_session()
                continue
            logger.exception(
                "Failed to fetch Yahoo Finance data for %s", ticker_symbol
            )
            return _fallback_scrape(stock_code, result)

    return _fallback_scrape(stock_code, result)


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
