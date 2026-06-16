from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from nasdaq_elt.config import Settings
from nasdaq_elt.db import build_snowflake_connection_kwargs, split_sql_statements


def make_settings(**overrides: str) -> Settings:
    values = {
        "alpha_vantage_api_key": "alpha-key",
        "snowflake_account": "org-account",
        "snowflake_user": "etl_user",
        "snowflake_password": "secret",
        "snowflake_role": "NASDAQ_ELT_ROLE",
        "snowflake_warehouse": "NASDAQ_ELT_WH",
        "snowflake_database": "NASDAQ_MARKET_DATA",
        "nasdaq_symbol_limit": 3,
        "load_start_date": date(2024, 1, 1),
        "symbols_path": Path("config/nasdaq100_symbols.csv"),
        "sql_path": Path("sql/snowflake"),
    }
    values.update(overrides)
    return Settings(**values)


def test_build_snowflake_connection_kwargs_uses_expected_database_context() -> None:
    kwargs = build_snowflake_connection_kwargs(make_settings())

    assert kwargs == {
        "account": "org-account",
        "user": "etl_user",
        "password": "secret",
        "database": "NASDAQ_MARKET_DATA",
        "schema": "UTIL",
        "warehouse": "NASDAQ_ELT_WH",
        "role": "NASDAQ_ELT_ROLE",
    }


def test_build_snowflake_connection_kwargs_rejects_missing_credentials() -> None:
    with pytest.raises(ValueError, match="SNOWFLAKE_ACCOUNT"):
        build_snowflake_connection_kwargs(make_settings(snowflake_account=""))


def test_split_sql_statements_preserves_semicolon_inside_strings() -> None:
    statements = split_sql_statements(
        "CREATE TABLE demo AS SELECT 'a;b' AS value; SELECT 1;"
    )

    assert statements == ["CREATE TABLE demo AS SELECT 'a;b' AS value", "SELECT 1"]
