"""Data quality checks for price staging data."""

from __future__ import annotations

from datetime import date

import pandas as pd


class DataQualityError(ValueError):
    """Raised when transformed data violates warehouse quality rules."""


def validate_price_frame(prices: pd.DataFrame, min_trading_date: date) -> None:
    required_columns = {
        "symbol",
        "trading_date",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
    }
    missing_columns = required_columns - set(prices.columns)
    if missing_columns:
        raise DataQualityError(f"Missing price columns: {sorted(missing_columns)}")

    if prices.empty:
        return

    null_key_rows = prices[["symbol", "trading_date"]].isna().any(axis=1).sum()
    if null_key_rows:
        raise DataQualityError(f"Found {null_key_rows} rows with null primary-key fields.")

    duplicate_rows = prices.duplicated(subset=["symbol", "trading_date"]).sum()
    if duplicate_rows:
        raise DataQualityError(f"Found {duplicate_rows} duplicate symbol/trading_date rows.")

    if (prices["trading_date"] < min_trading_date).any():
        raise DataQualityError("Found rows older than LOAD_START_DATE.")

    if (prices["volume"] < 0).any():
        raise DataQualityError("Found negative volume values.")

    if (prices["high_price"] < prices["low_price"]).any():
        raise DataQualityError("Found rows where high_price is below low_price.")
