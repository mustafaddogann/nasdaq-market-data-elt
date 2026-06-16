"""Snowflake warehouse helpers."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from nasdaq_elt.config import Settings


REQUIRED_SNOWFLAKE_FIELDS = [
    "snowflake_account",
    "snowflake_user",
    "snowflake_password",
    "snowflake_role",
    "snowflake_warehouse",
    "snowflake_database",
]


def build_snowflake_connection_kwargs(settings: Settings) -> dict[str, str]:
    missing_fields = [
        field_name for field_name in REQUIRED_SNOWFLAKE_FIELDS if not getattr(settings, field_name)
    ]
    if missing_fields:
        display_names = [field_name.upper() for field_name in missing_fields]
        raise ValueError(f"Missing Snowflake configuration: {', '.join(display_names)}")

    return {
        "account": settings.snowflake_account,
        "user": settings.snowflake_user,
        "password": settings.snowflake_password,
        "database": settings.snowflake_database,
        "schema": "UTIL",
        "warehouse": settings.snowflake_warehouse,
        "role": settings.snowflake_role,
    }


def make_engine(settings: Settings) -> Any:
    try:
        from snowflake.sqlalchemy import URL
        from sqlalchemy import create_engine
    except ImportError as exc:
        raise RuntimeError(
            "Snowflake dependencies are required. Install with `pip install -e .`."
        ) from exc

    return create_engine(URL(**build_snowflake_connection_kwargs(settings)), future=True)


def split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current_statement: list[str] = []
    in_single_quote = False

    for character in sql:
        if character == "'":
            in_single_quote = not in_single_quote

        if character == ";" and not in_single_quote:
            statement = "".join(current_statement).strip()
            if statement:
                statements.append(statement)
            current_statement = []
            continue

        current_statement.append(character)

    trailing_statement = "".join(current_statement).strip()
    if trailing_statement:
        statements.append(trailing_statement)

    return statements


def execute_sql_file(engine: Any, sql_file: Path) -> None:
    from sqlalchemy import text

    sql = sql_file.read_text(encoding="utf-8")
    with engine.begin() as connection:
        for statement in split_sql_statements(sql):
            connection.execute(text(statement))


def initialize_database(engine: Any, sql_path: Path) -> None:
    execute_sql_file(engine, sql_path / "schema.sql")


def build_gold_models(engine: Any, sql_path: Path) -> None:
    execute_sql_file(engine, sql_path / "build_gold.sql")


def insert_raw_api_response(
    engine: Any,
    symbol: str,
    request_params: dict[str, Any],
    response_payload: dict[str, Any],
    status_code: int,
    api_message: Optional[str] = None,
) -> int:
    from sqlalchemy import text

    ingestion_batch_id = str(uuid.uuid4())
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO BRONZE.RAW_API_RESPONSES (
                    INGESTION_BATCH_ID,
                    SOURCE_SYSTEM,
                    ENDPOINT,
                    SYMBOL,
                    REQUEST_PARAMS,
                    RESPONSE_PAYLOAD,
                    STATUS_CODE,
                    IS_SUCCESS,
                    API_MESSAGE
                )
                SELECT
                    :ingestion_batch_id,
                    'alpha_vantage',
                    'TIME_SERIES_DAILY',
                    :symbol,
                    PARSE_JSON(:request_params),
                    PARSE_JSON(:response_payload),
                    :status_code,
                    TRUE,
                    :api_message
                """
            ),
            {
                "ingestion_batch_id": ingestion_batch_id,
                "symbol": symbol,
                "request_params": json.dumps(request_params),
                "response_payload": json.dumps(response_payload),
                "status_code": status_code,
                "api_message": api_message,
            },
        )
        response_id = connection.execute(
            text(
                """
                SELECT RESPONSE_ID
                FROM BRONZE.RAW_API_RESPONSES
                WHERE INGESTION_BATCH_ID = :ingestion_batch_id
                """
            ),
            {"ingestion_batch_id": ingestion_batch_id},
        ).scalar_one()

    return int(response_id)


def normalize_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()

    if isinstance(value, (date, datetime)):
        return value

    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass

    if hasattr(value, "item"):
        return value.item()

    return value


def dataframe_records(dataframe: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for record in dataframe[columns].to_dict(orient="records"):
        records.append({column: normalize_value(value) for column, value in record.items()})
    return records


def upsert_dataframe(
    engine: Any,
    dataframe: pd.DataFrame,
    target_table: str,
    target_columns: list[str],
    conflict_columns: list[str],
    update_columns: list[str],
) -> None:
    if dataframe.empty:
        return

    from sqlalchemy import text

    temp_table_name = f"TMP_{target_table.replace('.', '_')}_{uuid.uuid4().hex[:10]}".upper()
    temp_table = f"UTIL.{temp_table_name}"
    insert_columns = ", ".join(column.upper() for column in target_columns)
    bind_columns = ", ".join(f":{column}" for column in target_columns)
    merge_condition = " AND ".join(
        f"TARGET.{column.upper()} = SOURCE.{column.upper()}" for column in conflict_columns
    )
    update_assignments = ", ".join(
        f"TARGET.{column.upper()} = SOURCE.{column.upper()}" for column in update_columns
    )
    update_clause = f"{update_assignments}, TARGET.LOADED_AT = CURRENT_TIMESTAMP()"
    insert_values = ", ".join(f"SOURCE.{column.upper()}" for column in target_columns)
    records = dataframe_records(dataframe, target_columns)

    with engine.begin() as connection:
        connection.execute(text(f"CREATE TEMPORARY TABLE {temp_table} LIKE {target_table}"))
        connection.execute(
            text(f"INSERT INTO {temp_table} ({insert_columns}) VALUES ({bind_columns})"),
            records,
        )
        connection.execute(
            text(
                f"""
                MERGE INTO {target_table} AS TARGET
                USING {temp_table} AS SOURCE
                    ON {merge_condition}
                WHEN MATCHED THEN UPDATE SET {update_clause}
                WHEN NOT MATCHED THEN INSERT ({insert_columns})
                    VALUES ({insert_values})
                """
            )
        )


def upsert_securities(engine: Any, securities: pd.DataFrame) -> None:
    upsert_dataframe(
        engine=engine,
        dataframe=securities,
        target_table="SILVER.STG_SECURITY",
        target_columns=["symbol", "company_name", "sector", "industry", "is_active"],
        conflict_columns=["symbol"],
        update_columns=["company_name", "sector", "industry", "is_active"],
    )


def upsert_daily_prices(
    engine: Any,
    prices: pd.DataFrame,
    raw_response_id: Optional[int] = None,
) -> None:
    prices_to_load = prices.copy()
    if raw_response_id is not None:
        prices_to_load["raw_response_id"] = raw_response_id

    bronze_columns = [
        "symbol",
        "trading_date",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
        "raw_response_id",
    ]
    silver_columns = [
        "symbol",
        "trading_date",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
        "source_last_refreshed",
    ]

    upsert_dataframe(
        engine=engine,
        dataframe=prices_to_load,
        target_table="BRONZE.RAW_NASDAQ_DAILY_PRICES",
        target_columns=bronze_columns,
        conflict_columns=["symbol", "trading_date"],
        update_columns=[
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
            "raw_response_id",
        ],
    )
    upsert_dataframe(
        engine=engine,
        dataframe=prices,
        target_table="SILVER.STG_DAILY_PRICE",
        target_columns=silver_columns,
        conflict_columns=["symbol", "trading_date"],
        update_columns=[
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
            "source_last_refreshed",
        ],
    )


def upsert_trading_calendar(engine: Any, calendar: pd.DataFrame) -> None:
    upsert_dataframe(
        engine=engine,
        dataframe=calendar,
        target_table="SILVER.STG_TRADING_CALENDAR",
        target_columns=["trading_date", "is_weekday"],
        conflict_columns=["trading_date"],
        update_columns=["is_weekday"],
    )
