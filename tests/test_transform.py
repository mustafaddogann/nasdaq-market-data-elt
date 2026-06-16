from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from nasdaq_elt.quality import DataQualityError, validate_price_frame
from nasdaq_elt.transform import (
    add_date_key,
    add_price_metrics,
    build_trading_calendar,
    filter_prices_from_start,
    parse_daily_prices,
)


def test_parse_daily_prices_returns_sorted_ohlcv_rows(alpha_vantage_daily_payload: dict) -> None:
    prices = parse_daily_prices("AAPL", alpha_vantage_daily_payload)

    assert list(prices["trading_date"]) == [
        date(2024, 1, 3),
        date(2024, 1, 4),
        date(2024, 1, 5),
        date(2024, 1, 8),
    ]
    assert prices.loc[0, "symbol"] == "AAPL"
    assert prices.loc[0, "close_price"] == 100.0
    assert prices.loc[0, "volume"] == 1200000


def test_filter_prices_from_start(alpha_vantage_daily_payload: dict) -> None:
    prices = parse_daily_prices("AAPL", alpha_vantage_daily_payload)
    filtered = filter_prices_from_start(prices, date(2024, 1, 5))

    assert list(filtered["trading_date"]) == [date(2024, 1, 5), date(2024, 1, 8)]


def test_add_price_metrics_computes_daily_return(alpha_vantage_daily_payload: dict) -> None:
    prices = parse_daily_prices("AAPL", alpha_vantage_daily_payload)
    metrics = add_price_metrics(prices)

    second_row = metrics.loc[metrics["trading_date"] == date(2024, 1, 4)].iloc[0]
    assert second_row["prior_close_price"] == 100.0
    assert second_row["daily_return"] == pytest.approx(0.02)


def test_build_trading_calendar_uses_loaded_dates(alpha_vantage_daily_payload: dict) -> None:
    prices = parse_daily_prices("AAPL", alpha_vantage_daily_payload)
    calendar = build_trading_calendar(prices)

    assert len(calendar) == 4
    assert calendar["is_weekday"].all()


def test_add_date_key_prepares_dimensional_date_key(alpha_vantage_daily_payload: dict) -> None:
    prices = parse_daily_prices("AAPL", alpha_vantage_daily_payload)
    dimensional_prices = add_date_key(prices)

    assert list(dimensional_prices["date_key"]) == [20240103, 20240104, 20240105, 20240108]


def test_quality_check_rejects_duplicate_symbol_date(alpha_vantage_daily_payload: dict) -> None:
    prices = parse_daily_prices("AAPL", alpha_vantage_daily_payload)
    duplicated = pd.concat([prices, prices.head(1)], ignore_index=True)

    with pytest.raises(DataQualityError, match="duplicate"):
        validate_price_frame(duplicated, date(2024, 1, 1))
