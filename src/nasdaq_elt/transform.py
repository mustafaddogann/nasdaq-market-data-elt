"""Transform Alpha Vantage responses into warehouse-ready data frames."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from nasdaq_elt.alpha_vantage import TIME_SERIES_DAILY_KEY


REQUIRED_SECURITY_COLUMNS = ["symbol", "company_name", "sector", "industry"]
PRICE_COLUMNS = [
    "symbol",
    "trading_date",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    "source_last_refreshed",
]


def load_symbol_universe(symbols_path: Path, limit: int) -> pd.DataFrame:
    symbols = pd.read_csv(symbols_path)
    missing_columns = set(REQUIRED_SECURITY_COLUMNS) - set(symbols.columns)
    if missing_columns:
        raise ValueError(f"Missing symbol config columns: {sorted(missing_columns)}")

    symbols = symbols.sort_values("priority", kind="stable").head(limit).copy()
    symbols["symbol"] = symbols["symbol"].str.upper().str.strip()
    symbols["is_active"] = True
    return symbols[["symbol", "company_name", "sector", "industry", "is_active"]]


def parse_daily_prices(symbol: str, payload: dict[str, Any]) -> pd.DataFrame:
    if TIME_SERIES_DAILY_KEY not in payload:
        raise ValueError(f"Missing '{TIME_SERIES_DAILY_KEY}' for {symbol}.")

    last_refreshed = payload.get("Meta Data", {}).get("3. Last Refreshed")
    records: list[dict[str, Any]] = []
    for trading_date, values in payload[TIME_SERIES_DAILY_KEY].items():
        records.append(
            {
                "symbol": symbol.upper(),
                "trading_date": pd.to_datetime(trading_date).date(),
                "open_price": float(values["1. open"]),
                "high_price": float(values["2. high"]),
                "low_price": float(values["3. low"]),
                "close_price": float(values["4. close"]),
                "volume": int(values["5. volume"]),
                "source_last_refreshed": last_refreshed,
            }
        )

    prices = pd.DataFrame.from_records(records, columns=PRICE_COLUMNS)
    if prices.empty:
        return prices

    return prices.sort_values(["symbol", "trading_date"], kind="stable").reset_index(drop=True)


def filter_prices_from_start(prices: pd.DataFrame, load_start_date: date) -> pd.DataFrame:
    if prices.empty:
        return prices
    return prices[prices["trading_date"] >= load_start_date].copy()


def build_trading_calendar(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        return pd.DataFrame(columns=["trading_date", "is_weekday"])

    calendar = prices[["trading_date"]].drop_duplicates().sort_values("trading_date").copy()
    calendar["is_weekday"] = pd.to_datetime(calendar["trading_date"]).dt.weekday < 5
    return calendar


def add_date_key(dataframe: pd.DataFrame, date_column: str = "trading_date") -> pd.DataFrame:
    if dataframe.empty:
        output = dataframe.copy()
        output["date_key"] = pd.Series(dtype="int64")
        return output

    output = dataframe.copy()
    output["date_key"] = pd.to_datetime(output[date_column]).dt.strftime("%Y%m%d").astype("int64")
    return output


def add_price_metrics(prices: pd.DataFrame) -> pd.DataFrame:
    """Add analytics metrics used by tests and mirrors Gold SQL model logic."""

    if prices.empty:
        return prices

    metrics = prices.sort_values(["symbol", "trading_date"], kind="stable").copy()
    grouped = metrics.groupby("symbol", group_keys=False)
    metrics["prior_close_price"] = grouped["close_price"].shift(1)
    metrics["daily_return"] = grouped["close_price"].pct_change()
    metrics["rolling_7_day_return"] = grouped["close_price"].pct_change(periods=7)
    metrics["rolling_30_day_return"] = grouped["close_price"].pct_change(periods=30)
    metrics["rolling_7_day_volatility"] = (
        grouped["daily_return"].rolling(7).std().reset_index(level=0, drop=True)
    )
    metrics["ma_7_close_price"] = (
        grouped["close_price"].rolling(7).mean().reset_index(level=0, drop=True)
    )
    metrics["ma_30_close_price"] = (
        grouped["close_price"].rolling(30).mean().reset_index(level=0, drop=True)
    )
    metrics["avg_30_day_volume"] = (
        grouped["volume"].rolling(30).mean().reset_index(level=0, drop=True)
    )
    metrics["volume_spike_flag"] = metrics["volume"] > (metrics["avg_30_day_volume"] * 2)
    metrics["moving_average_signal"] = "insufficient_history"
    metrics.loc[
        metrics["ma_7_close_price"].notna()
        & metrics["ma_30_close_price"].notna()
        & (metrics["ma_7_close_price"] > metrics["ma_30_close_price"]),
        "moving_average_signal",
    ] = "bullish"
    metrics.loc[
        metrics["ma_7_close_price"].notna()
        & metrics["ma_30_close_price"].notna()
        & (metrics["ma_7_close_price"] <= metrics["ma_30_close_price"]),
        "moving_average_signal",
    ] = "bearish"
    metrics["top_gainer_rank"] = metrics.groupby("trading_date")["daily_return"].rank(
        method="dense", ascending=False
    )
    metrics["top_loser_rank"] = metrics.groupby("trading_date")["daily_return"].rank(
        method="dense", ascending=True
    )
    return metrics
