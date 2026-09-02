import json
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_http_client


def install_upstream(handler):
    """Point the endpoint's upstream dependency at a fake transport — no
    network involved, so this works even with FX_UPSTREAM_BASE pointed at
    a closed port."""
    transport = httpx.MockTransport(handler)
    mock_client = httpx.AsyncClient(transport=transport, base_url="http://upstream.test")
    app.dependency_overrides[get_http_client] = lambda: mock_client
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def json_response(payload, status_code=200):
    def handler(request):
        return httpx.Response(status_code, json=payload)

    return handler


def counting(handler):
    calls = []

    def wrapped(request):
        calls.append(request)
        return handler(request)

    return wrapped, calls


def unexpected_call_handler(request):
    raise AssertionError("upstream should not have been called for: {}".format(request.url))


def test_convert_happy_path():
    handler = json_response({"amount": 1.0, "base": "EUR", "date": "2026-08-28", "rates": {"TRY": 47.1234}})
    client = install_upstream(handler)

    response = client.get("/tools/convert", params={"amount": "250", "from": "EUR", "to": "TRY", "date": "2026-08-28"})

    assert response.status_code == 200
    body = response.json()
    assert body["rate"] == 47.1234
    assert body["result"] == round(250 * 47.1234, 2)
    assert body["rate_date"] == "2026-08-28"
    assert body["asked_date"] == "2026-08-28"
    assert body["source"] == "ECB via frankfurter.dev"


def test_convert_weekend_falls_back_and_says_so():
    # Asked for Saturday 2026-08-29; upstream (like the real one) resolves
    # this to Friday 2026-08-28 and reports that date back.
    handler = json_response({"amount": 1.0, "base": "EUR", "date": "2026-08-28", "rates": {"TRY": 47.0}})
    client = install_upstream(handler)

    response = client.get("/tools/convert", params={"amount": "10", "from": "EUR", "to": "TRY", "date": "2026-08-29"})

    assert response.status_code == 200
    body = response.json()
    assert body["asked_date"] == "2026-08-29"
    assert body["rate_date"] == "2026-08-28"
    assert body["rate_date"] != body["asked_date"]


def test_convert_same_currency_skips_upstream():
    client = install_upstream(unexpected_call_handler)

    response = client.get("/tools/convert", params={"amount": "10", "from": "EUR", "to": "EUR", "date": "2026-08-28"})

    assert response.status_code == 200
    body = response.json()
    assert body["rate"] == 1.0
    assert body["result"] == 10.0


@pytest.mark.parametrize(
    "params,expected_code",
    [
        ({"amount": "0", "from": "EUR", "to": "TRY"}, "invalid_amount"),
        ({"amount": "-5", "from": "EUR", "to": "TRY"}, "invalid_amount"),
        ({"from": "EUR", "to": "TRY"}, "invalid_amount"),
        ({"amount": "1.2345678901", "from": "EUR", "to": "TRY"}, "invalid_amount"),
        ({"amount": "10", "from": "ZZZ", "to": "TRY"}, "invalid_currency"),
        ({"amount": "10", "from": "EUR", "to": "ZZZ"}, "invalid_currency"),
        ({"amount": "10", "from": "EUR", "to": "TRY", "date": "not-a-date"}, "invalid_date"),
        ({"amount": "10", "from": "EUR", "to": "TRY", "date": "2099-01-01"}, "future_date"),
        ({"amount": "10", "from": "EUR", "to": "TRY", "date": "1990-01-01"}, "date_before_series_start"),
    ],
)
def test_convert_rejects_bad_input_without_calling_upstream(params, expected_code):
    client = install_upstream(unexpected_call_handler)

    response = client.get("/tools/convert", params=params)

    assert response.status_code >= 400
    body = response.json()
    assert body["error"] == expected_code
    assert "message" in body


def test_convert_upstream_500_is_reported_as_unavailable():
    handler = json_response({"message": "internal error"}, status_code=500)
    client = install_upstream(handler)

    response = client.get("/tools/convert", params={"amount": "10", "from": "EUR", "to": "TRY", "date": "2026-08-28"})

    assert response.status_code == 502
    assert response.json()["error"] == "upstream_unavailable"


def test_convert_upstream_non_json_is_reported_as_unavailable():
    def handler(request):
        return httpx.Response(200, text="<html>not json</html>")

    client = install_upstream(handler)

    response = client.get("/tools/convert", params={"amount": "10", "from": "EUR", "to": "TRY", "date": "2026-08-28"})

    assert response.status_code == 502
    assert response.json()["error"] == "upstream_unavailable"


def test_convert_upstream_timeout_is_reported_as_unavailable():
    def handler(request):
        raise httpx.TimeoutException("connect timed out", request=request)

    client = install_upstream(handler)

    response = client.get("/tools/convert", params={"amount": "10", "from": "EUR", "to": "TRY", "date": "2026-08-28"})

    assert response.status_code == 502
    assert response.json()["error"] == "upstream_unavailable"


def test_convert_upstream_404_after_valid_input_is_no_rate_available():
    handler = json_response({"message": "not found"}, status_code=404)
    client = install_upstream(handler)

    response = client.get("/tools/convert", params={"amount": "10", "from": "EUR", "to": "TRY", "date": "2026-08-28"})

    assert response.status_code == 404
    assert response.json()["error"] == "no_rate_available"


def test_convert_caches_repeat_query_without_calling_upstream_again():
    handler, calls = counting(
        json_response({"amount": 1.0, "base": "EUR", "date": "2026-08-28", "rates": {"TRY": 47.0}})
    )
    client = install_upstream(handler)
    params = {"amount": "10", "from": "EUR", "to": "TRY", "date": "2026-08-28"}

    first = client.get("/tools/convert", params=params)
    second = client.get("/tools/convert", params=params)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert len(calls) == 1


def test_convert_defaults_date_to_today_when_omitted():
    today = datetime.now(timezone.utc).date().isoformat()
    handler = json_response({"amount": 1.0, "base": "EUR", "date": today, "rates": {"TRY": 47.0}})
    client = install_upstream(handler)

    response = client.get("/tools/convert", params={"amount": "10", "from": "EUR", "to": "TRY"})

    assert response.status_code == 200
    assert response.json()["asked_date"] == today
