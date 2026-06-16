from __future__ import annotations

import pytest

from nasdaq_elt.alpha_vantage import AlphaVantageClient, AlphaVantageRateLimitError


class FakeResponse:
    status_code = 200

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = []

    def get(self, url: str, params: dict, timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(self.payload)


def test_client_requires_api_key() -> None:
    with pytest.raises(ValueError, match="ALPHA_VANTAGE_API_KEY"):
        AlphaVantageClient(api_key="")


def test_fetch_daily_prices_builds_expected_request(alpha_vantage_daily_payload: dict) -> None:
    session = FakeSession(alpha_vantage_daily_payload)
    client = AlphaVantageClient(api_key="test-key", session=session)

    response = client.fetch_daily_prices("AAPL", outputsize="compact")

    assert response.symbol == "AAPL"
    assert response.status_code == 200
    assert response.request_params["function"] == "TIME_SERIES_DAILY"
    assert response.request_params["symbol"] == "AAPL"
    assert "apikey" not in response.request_params
    assert session.calls[0]["params"]["apikey"] == "test-key"


def test_rate_limit_response_raises_rate_limit_error() -> None:
    session = FakeSession({"Note": "Our standard API rate limit is 25 requests per day."})
    client = AlphaVantageClient(api_key="test-key", session=session)

    with pytest.raises(AlphaVantageRateLimitError):
        client.fetch_daily_prices("AAPL")
