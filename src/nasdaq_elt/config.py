"""Runtime configuration for the Nasdaq-100 market data pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path


DEFAULT_SYMBOLS_PATH = Path("config/nasdaq100_symbols.csv")
DEFAULT_SQL_PATH = Path("sql/snowflake")


@dataclass(frozen=True)
class Settings:
    alpha_vantage_api_key: str
    snowflake_account: str
    snowflake_user: str
    snowflake_password: str
    snowflake_role: str
    snowflake_warehouse: str
    snowflake_database: str
    nasdaq_symbol_limit: int
    load_start_date: date
    symbols_path: Path
    sql_path: Path
    alpha_vantage_base_url: str = "https://www.alphavantage.co/query"
    alpha_vantage_outputsize: str = "compact"
    alpha_vantage_api_pause_seconds: float = 12.5
    alpha_vantage_timeout_seconds: int = 30


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def load_settings() -> Settings:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    return Settings(
        alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY", "").strip(),
        snowflake_account=os.getenv("SNOWFLAKE_ACCOUNT", "").strip(),
        snowflake_user=os.getenv("SNOWFLAKE_USER", "").strip(),
        snowflake_password=os.getenv("SNOWFLAKE_PASSWORD", "").strip(),
        snowflake_role=os.getenv("SNOWFLAKE_ROLE", "NASDAQ_ELT_ROLE").strip(),
        snowflake_warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "NASDAQ_ELT_WH").strip(),
        snowflake_database=os.getenv("SNOWFLAKE_DATABASE", "NASDAQ_MARKET_DATA").strip(),
        nasdaq_symbol_limit=int(os.getenv("NASDAQ_SYMBOL_LIMIT", "25")),
        load_start_date=parse_date(os.getenv("LOAD_START_DATE", "2024-01-01")),
        symbols_path=Path(os.getenv("NASDAQ_SYMBOLS_PATH", DEFAULT_SYMBOLS_PATH)),
        sql_path=Path(os.getenv("SQL_PATH", DEFAULT_SQL_PATH)),
        alpha_vantage_base_url=os.getenv(
            "ALPHA_VANTAGE_BASE_URL", "https://www.alphavantage.co/query"
        ),
        alpha_vantage_outputsize=os.getenv("ALPHA_VANTAGE_OUTPUTSIZE", "compact"),
        alpha_vantage_api_pause_seconds=float(os.getenv("ALPHA_VANTAGE_API_PAUSE_SECONDS", "12.5")),
        alpha_vantage_timeout_seconds=int(os.getenv("ALPHA_VANTAGE_TIMEOUT_SECONDS", "30")),
    )
