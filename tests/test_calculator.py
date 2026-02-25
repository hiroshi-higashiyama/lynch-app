"""Tests for the Peter Lynch Index calculator."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.calculator import calculate_lynch_indices


def test_basic_calculation():
    """Test with all values provided."""
    result = calculate_lynch_indices(
        per=15.0,
        dividend_yield=2.5,
        eps_current=200.0,
        eps_previous=150.0,
        eps_forecast=250.0,
        ordinary_income_current=5000.0,
        ordinary_income_previous=4000.0,
        ordinary_income_two_years_ago=3000.0,
        ordinary_income_forecast=6000.0,
    )

    indices = result["indices"]
    assert len(indices) == 4

    # EPS growth: (200-150)/150*100 = 33.33%
    # Lynch index (EPS current): (33.33 + 2.5) / 15 = 2.39
    idx0 = indices[0]
    assert idx0["name"] == "当期実績EPSベース"
    assert idx0["index_value"] is not None
    assert abs(idx0["index_value"] - 2.389) < 0.01
    assert idx0["evaluation"] == "投資対象"

    # EPS forecast growth: (250-150)/150*100 = 66.67%
    # Lynch index (EPS forecast): (66.67 + 2.5) / 15 = 4.61
    idx1 = indices[1]
    assert idx1["name"] == "来期予想EPSベース"
    assert idx1["index_value"] is not None
    assert abs(idx1["index_value"] - 4.611) < 0.01
    assert idx1["evaluation"] == "投資対象"

    # OI avg growth: [((4000/3000)*100-100) + ((5000/4000)*100-100)] / 2
    #              = [(133.33-100) + (125-100)] / 2 = (33.33+25)/2 = 29.17%
    # Lynch index: (29.17 + 2.5) / 15 = 2.11
    idx2 = indices[2]
    assert idx2["name"] == "当期実績経常利益ベース"
    assert idx2["index_value"] is not None
    assert abs(idx2["index_value"] - 2.111) < 0.01
    assert idx2["evaluation"] == "投資対象"

    # OI forecast avg growth: [((4000/3000)*100-100) + ((6000/4000)*100-100)] / 2
    #                        = [(33.33) + (50)] / 2 = 41.67%
    # Lynch index: (41.67 + 2.5) / 15 = 2.94
    idx3 = indices[3]
    assert idx3["name"] == "来期予想経常利益ベース"
    assert idx3["index_value"] is not None
    assert abs(idx3["index_value"] - 2.944) < 0.01
    assert idx3["evaluation"] == "投資対象"


def test_fair_evaluation():
    """Test 'まずまず' evaluation (1.5 <= index < 2.0)."""
    result = calculate_lynch_indices(
        per=20.0,
        dividend_yield=1.0,
        eps_current=120.0,
        eps_previous=100.0,
        eps_forecast=None,
        ordinary_income_current=None,
        ordinary_income_previous=None,
        ordinary_income_two_years_ago=None,
        ordinary_income_forecast=None,
    )

    # EPS growth: (120-100)/100*100 = 20%
    # Lynch: (20 + 1) / 20 = 1.05
    idx0 = result["indices"][0]
    assert abs(idx0["index_value"] - 1.05) < 0.01
    assert idx0["evaluation"] == "見込み薄"


def test_missing_data_returns_na():
    """Test that missing data results in N/A evaluations."""
    result = calculate_lynch_indices(
        per=10.0,
        dividend_yield=3.0,
        eps_current=None,
        eps_previous=None,
        eps_forecast=None,
        ordinary_income_current=None,
        ordinary_income_previous=None,
        ordinary_income_two_years_ago=None,
        ordinary_income_forecast=None,
    )

    for idx in result["indices"]:
        assert idx["index_value"] is None
        assert idx["evaluation"] == "算出不可"


def test_zero_per_returns_none():
    """Test that PER of zero doesn't cause division error."""
    result = calculate_lynch_indices(
        per=0.0,
        dividend_yield=2.0,
        eps_current=100.0,
        eps_previous=80.0,
        eps_forecast=120.0,
        ordinary_income_current=5000.0,
        ordinary_income_previous=4000.0,
        ordinary_income_two_years_ago=3000.0,
        ordinary_income_forecast=6000.0,
    )

    for idx in result["indices"]:
        assert idx["index_value"] is None


def test_negative_growth():
    """Test with declining EPS (negative growth)."""
    result = calculate_lynch_indices(
        per=10.0,
        dividend_yield=3.0,
        eps_current=80.0,
        eps_previous=100.0,
        eps_forecast=70.0,
        ordinary_income_current=3000.0,
        ordinary_income_previous=4000.0,
        ordinary_income_two_years_ago=5000.0,
        ordinary_income_forecast=2500.0,
    )

    # EPS growth: (80-100)/100*100 = -20%
    # Lynch: (-20 + 3) / 10 = -1.7
    idx0 = result["indices"][0]
    assert idx0["index_value"] is not None
    assert idx0["index_value"] < 0
    assert idx0["evaluation"] == "見込み薄"


def test_input_data_formatting():
    """Test that input data is formatted correctly."""
    result = calculate_lynch_indices(
        per=15.5,
        dividend_yield=2.3,
        eps_current=123.45,
        eps_previous=100.0,
        eps_forecast=None,
        ordinary_income_current=1234567.0,
        ordinary_income_previous=1000000.0,
        ordinary_income_two_years_ago=800000.0,
        ordinary_income_forecast=None,
    )

    data = result["input_data"]
    assert data["per"] == "15.50"
    assert data["dividend_yield"] == "2.30"
    assert data["eps_current"] == "123.45"
    assert data["eps_forecast"] == "N/A"
    assert data["ordinary_income_current"] == "1,234,567"
    assert data["ordinary_income_forecast"] == "N/A"
