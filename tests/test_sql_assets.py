from __future__ import annotations

from pathlib import Path


def test_schema_contains_bronze_silver_gold_tables() -> None:
    schema_sql = Path("sql/snowflake/schema.sql").read_text(encoding="utf-8")

    for expected_table in [
        "BRONZE.RAW_API_RESPONSES",
        "BRONZE.RAW_NASDAQ_DAILY_PRICES",
        "SILVER.STG_SECURITY",
        "SILVER.STG_DAILY_PRICE",
        "SILVER.STG_TRADING_CALENDAR",
        "GOLD.DIM_DATE",
        "GOLD.DIM_SECURITY",
        "GOLD.DIM_SECTOR",
        "GOLD.FACT_DAILY_PRICE",
        "GOLD.FACT_SECURITY_DAILY_METRICS",
    ]:
        assert expected_table in schema_sql


def test_gold_sql_builds_expected_metrics() -> None:
    build_gold_sql = Path("sql/snowflake/build_gold.sql").read_text(encoding="utf-8")

    for expected_metric in [
        "DAILY_RETURN",
        "ROLLING_7_DAY_RETURN",
        "ROLLING_30_DAY_RETURN",
        "ROLLING_7_DAY_VOLATILITY",
        "VOLUME_SPIKE_FLAG",
        "MOVING_AVERAGE_SIGNAL",
        "TOP_GAINER_RANK",
        "TOP_LOSER_RANK",
        "RANK_MOVEMENT",
    ]:
        assert expected_metric in build_gold_sql


def test_snowflake_sql_uses_cloud_warehouse_features() -> None:
    schema_sql = Path("sql/snowflake/schema.sql").read_text(encoding="utf-8")
    build_gold_sql = Path("sql/snowflake/build_gold.sql").read_text(encoding="utf-8")
    db_code = Path("src/nasdaq_elt/db.py").read_text(encoding="utf-8")

    for expected in ["VARIANT", "AUTOINCREMENT"]:
        assert expected in schema_sql

    for expected in ["CREATE OR REPLACE TABLE", "QUALIFY"]:
        assert expected in build_gold_sql

    assert "MERGE INTO" in db_code


def test_gold_sql_builds_expected_marts() -> None:
    build_gold_sql = Path("sql/snowflake/build_gold.sql").read_text(encoding="utf-8")

    for expected_mart in [
        "GOLD.MART_NASDAQ_MARKET_MOMENTUM",
        "GOLD.MART_SECTOR_PERFORMANCE",
        "GOLD.MART_TOP_MOVERS",
        "GOLD.MART_SECURITY_TREND_SIGNALS",
    ]:
        assert expected_mart in build_gold_sql


def test_gold_sql_builds_surrogate_keys() -> None:
    build_gold_sql = Path("sql/snowflake/build_gold.sql").read_text(encoding="utf-8")

    assert "TO_NUMBER(TO_CHAR(TRADING_DATE, 'YYYYMMDD')) AS DATE_KEY" in build_gold_sql
    assert "ABS(HASH(SECTOR, INDUSTRY)) AS SECTOR_KEY" in build_gold_sql
    assert "ABS(HASH(s.SYMBOL)) AS SECURITY_KEY" in build_gold_sql
