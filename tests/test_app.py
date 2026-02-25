"""Tests for the Flask application routes."""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app


def get_client():
    app.config["TESTING"] = True
    return app.test_client()


def test_index_page():
    """Test that the index page loads."""
    client = get_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "ピーター・リンチ指数".encode("utf-8") in resp.data


def test_api_invalid_code_empty():
    """Test API rejects empty stock code."""
    client = get_client()
    resp = client.post(
        "/api/calculate",
        data=json.dumps({"stock_code": ""}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_api_invalid_code_letters():
    """Test API rejects non-numeric codes."""
    client = get_client()
    resp = client.post(
        "/api/calculate",
        data=json.dumps({"stock_code": "abcd"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_api_invalid_code_too_short():
    """Test API rejects codes shorter than 4 digits."""
    client = get_client()
    resp = client.post(
        "/api/calculate",
        data=json.dumps({"stock_code": "123"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_api_invalid_code_too_long():
    """Test API rejects codes longer than 4 digits."""
    client = get_client()
    resp = client.post(
        "/api/calculate",
        data=json.dumps({"stock_code": "12345"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_api_no_body():
    """Test API handles missing request body."""
    client = get_client()
    resp = client.post("/api/calculate", content_type="application/json")
    assert resp.status_code == 400
