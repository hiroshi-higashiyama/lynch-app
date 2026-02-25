"""EDINET API client for fetching financial statements (EPS, ordinary income)."""

import io
import logging
import re
import zipfile
from datetime import date, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import Config

logger = logging.getLogger(__name__)

EDINET_API_BASE = "https://api.edinet-fsa.go.jp/api/v2"


def _search_documents(edinet_code: str, api_key: str, doc_type_code: str = "120") -> list[dict]:
    """Search EDINET for filing documents of a given company.

    doc_type_code 120 = 有価証券報告書 (annual securities report)
    doc_type_code 140 = 四半期報告書 (quarterly report)
    """
    results = []
    end_date = date.today()
    start_date = end_date - timedelta(days=365 * 4)
    current = start_date

    while current <= end_date:
        params = {
            "date": current.strftime("%Y-%m-%d"),
            "type": 2,
            "Subscription-Key": api_key,
        }
        try:
            resp = requests.get(
                f"{EDINET_API_BASE}/documents.json", params=params, timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                for doc in data.get("results", []):
                    if (
                        doc.get("edinetCode") == edinet_code
                        and doc.get("docTypeCode") == doc_type_code
                    ):
                        results.append(doc)
        except requests.RequestException:
            logger.warning("EDINET API request failed for date %s", current)
        current += timedelta(days=1)

    return results


def _download_xbrl(doc_id: str, api_key: str) -> Optional[bytes]:
    """Download XBRL ZIP for a document."""
    params = {"type": 1, "Subscription-Key": api_key}
    try:
        resp = requests.get(
            f"{EDINET_API_BASE}/documents/{doc_id}", params=params, timeout=60
        )
        if resp.status_code == 200:
            return resp.content
    except requests.RequestException:
        logger.exception("Failed to download XBRL for doc %s", doc_id)
    return None


def _extract_xbrl_value(xbrl_content: str, tag_patterns: list[str]) -> Optional[float]:
    """Extract a numeric value from XBRL content by tag name patterns."""
    soup = BeautifulSoup(xbrl_content, "lxml-xml")
    for pattern in tag_patterns:
        elements = soup.find_all(re.compile(pattern, re.IGNORECASE))
        for elem in elements:
            text = elem.get_text(strip=True)
            text = text.replace(",", "").replace("△", "-")
            try:
                return float(text)
            except ValueError:
                continue
    return None


def _parse_xbrl_from_zip(zip_bytes: bytes) -> dict:
    """Parse XBRL files inside a ZIP archive and extract financial data."""
    data = {
        "ordinary_income": None,
        "net_income": None,
        "shares_outstanding": None,
        "eps": None,
        "forecast_ordinary_income": None,
        "forecast_eps": None,
    }

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            xbrl_files = [
                name
                for name in zf.namelist()
                if name.endswith(".xbrl") or name.endswith(".xml")
            ]

            for fname in xbrl_files:
                content = zf.read(fname).decode("utf-8", errors="replace")

                if data["ordinary_income"] is None:
                    data["ordinary_income"] = _extract_xbrl_value(
                        content,
                        [
                            r"OrdinaryIncomeLoss$",
                            r"OrdinaryIncomeLossSummaryOfBusinessResults",
                            r"OrdinaryIncome$",
                        ],
                    )

                if data["net_income"] is None:
                    data["net_income"] = _extract_xbrl_value(
                        content,
                        [
                            r"ProfitLossAttributableToOwnersOfParent$",
                            r"NetIncomeLoss$",
                            r"ProfitLoss$",
                        ],
                    )

                if data["shares_outstanding"] is None:
                    data["shares_outstanding"] = _extract_xbrl_value(
                        content,
                        [
                            r"NumberOfIssuedSharesAsOfEndOfPeriod",
                            r"TotalNumberOfIssuedShares",
                        ],
                    )

                if data["eps"] is None:
                    data["eps"] = _extract_xbrl_value(
                        content,
                        [
                            r"BasicEarningsLossPerShare$",
                            r"EarningsPerShare$",
                        ],
                    )

                if data["forecast_ordinary_income"] is None:
                    data["forecast_ordinary_income"] = _extract_xbrl_value(
                        content,
                        [
                            r"ForecastOrdinaryIncome",
                            r"OrdinaryIncomeLossForecast",
                        ],
                    )

                if data["forecast_eps"] is None:
                    data["forecast_eps"] = _extract_xbrl_value(
                        content,
                        [
                            r"ForecastBasicEarningsPerShare",
                            r"BasicEarningsLossPerShareForecast",
                        ],
                    )

    except (zipfile.BadZipFile, Exception):
        logger.exception("Failed to parse XBRL from ZIP")

    return data


def _edinet_code_from_stock_code(stock_code: str, api_key: str) -> Optional[str]:
    """Look up the EDINET code for a given stock code.

    Uses the EDINET code list API endpoint.
    """
    try:
        params = {"type": 2, "Subscription-Key": api_key}
        resp = requests.get(
            f"{EDINET_API_BASE}/codes.json", params=params, timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            for entry in data.get("results", []):
                sec_code = entry.get("secCode", "")
                # EDINET secCode is 5 digits (4-digit code + check digit)
                if sec_code and sec_code[:4] == stock_code:
                    return entry.get("edinetCode")
    except requests.RequestException:
        logger.exception("Failed to look up EDINET code for %s", stock_code)
    return None


def fetch_edinet_data(stock_code: str) -> dict:
    """Fetch EPS and ordinary income data from EDINET.

    Returns dict with keys:
        eps_current, eps_previous, eps_forecast,
        ordinary_income_current, ordinary_income_previous,
        ordinary_income_two_years_ago, ordinary_income_forecast
    """
    result = {
        "eps_current": None,
        "eps_previous": None,
        "eps_forecast": None,
        "ordinary_income_current": None,
        "ordinary_income_previous": None,
        "ordinary_income_two_years_ago": None,
        "ordinary_income_forecast": None,
        "data_source": "EDINET",
    }

    api_key = Config.EDINET_API_KEY
    if not api_key:
        logger.warning("EDINET_API_KEY not configured; skipping EDINET fetch")
        result["data_source"] = "EDINET (APIキー未設定)"
        return result

    edinet_code = _edinet_code_from_stock_code(stock_code, api_key)
    if not edinet_code:
        logger.warning("Could not find EDINET code for stock %s", stock_code)
        result["data_source"] = "EDINET (銘柄コード不明)"
        return result

    # Find annual reports (有価証券報告書)
    docs = _search_documents(edinet_code, api_key, doc_type_code="120")
    docs.sort(key=lambda d: d.get("periodEnd", ""), reverse=True)

    fiscal_data = []
    for doc in docs[:3]:
        zip_bytes = _download_xbrl(doc["docID"], api_key)
        if zip_bytes:
            parsed = _parse_xbrl_from_zip(zip_bytes)
            parsed["period_end"] = doc.get("periodEnd", "")
            fiscal_data.append(parsed)

    if len(fiscal_data) >= 1:
        latest = fiscal_data[0]
        result["eps_current"] = latest.get("eps")
        result["ordinary_income_current"] = latest.get("ordinary_income")
        result["eps_forecast"] = latest.get("forecast_eps")
        result["ordinary_income_forecast"] = latest.get("forecast_ordinary_income")

    if len(fiscal_data) >= 2:
        prev = fiscal_data[1]
        result["eps_previous"] = prev.get("eps")
        result["ordinary_income_previous"] = prev.get("ordinary_income")

    if len(fiscal_data) >= 3:
        two_ago = fiscal_data[2]
        result["ordinary_income_two_years_ago"] = two_ago.get("ordinary_income")

    return result
