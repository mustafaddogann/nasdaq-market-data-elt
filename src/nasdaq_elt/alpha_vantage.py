"""Alpha Vantage client for daily Nasdaq-100 price data."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import requests


TIME_SERIES_DAILY_KEY = "Time Series (Daily)"


class AlphaVantageError(RuntimeError):
    """Base exception for Alpha Vantage API failures."""


class AlphaVantageRateLimitError(AlphaVantageError):
    """Raised when Alpha Vantage returns a rate-limit or premium-plan response."""


@dataclass(frozen=True)
class AlphaVantageResponse:
    symbol: str
    request_params: dict[str, Any]
    payload: dict[str, Any]
    status_code: int
    api_message: Optional[str] = None


class AlphaVantageClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://www.alphavantage.co/query",
        timeout_seconds: int = 30,
        max_retries: int = 3,
        retry_backoff_seconds: float = 2.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY is required for live ingestion.")

        self.api_key = api_key
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.session = session or requests.Session()

    def fetch_daily_prices(self, symbol: str, outputsize: str = "compact") -> AlphaVantageResponse:
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": outputsize,
            "datatype": "json",
            "apikey": self.api_key,
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(
                    self.base_url,
                    params=params,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                api_message = extract_api_message(payload)
                validate_daily_payload(symbol=symbol, payload=payload, api_message=api_message)
                return AlphaVantageResponse(
                    symbol=symbol,
                    request_params={key: value for key, value in params.items() if key != "apikey"},
                    payload=payload,
                    status_code=response.status_code,
                    api_message=api_message,
                )
            except AlphaVantageRateLimitError:
                raise
            except (requests.RequestException, ValueError, AlphaVantageError) as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(self.retry_backoff_seconds * attempt)

        raise AlphaVantageError(f"Failed to fetch {symbol} after retries: {last_error}")


def extract_api_message(payload: dict[str, Any]) -> Optional[str]:
    for key in ("Note", "Information", "Error Message"):
        if key in payload:
            return str(payload[key])
    return None


def validate_daily_payload(
    symbol: str,
    payload: dict[str, Any],
    api_message: Optional[str] = None,
) -> None:
    if "Error Message" in payload:
        raise AlphaVantageError(
            f"Alpha Vantage rejected symbol {symbol}: {payload['Error Message']}"
        )

    if api_message and TIME_SERIES_DAILY_KEY not in payload:
        lowered = api_message.lower()
        if "rate limit" in lowered or "standard api rate limit" in lowered or "premium" in lowered:
            raise AlphaVantageRateLimitError(api_message)
        raise AlphaVantageError(api_message)

    if TIME_SERIES_DAILY_KEY not in payload:
        raise AlphaVantageError(f"Missing '{TIME_SERIES_DAILY_KEY}' in response for {symbol}.")
