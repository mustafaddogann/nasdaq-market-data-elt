from __future__ import annotations

import os
from pathlib import Path

import pytest

from nasdaq_elt.config import load_settings


@pytest.mark.integration
def test_snowflake_schema_and_gold_sql_execute_when_enabled() -> None:
    if os.getenv("SNOWFLAKE_TEST_ENABLED", "").lower() != "true":
        pytest.skip("Set SNOWFLAKE_TEST_ENABLED=true to run Snowflake integration tests.")

    pytest.importorskip("snowflake.sqlalchemy")
    pytest.importorskip("sqlalchemy")

    from nasdaq_elt.db import build_gold_models, initialize_database, make_engine

    settings = load_settings()
    engine = make_engine(settings)
    initialize_database(engine, Path("sql/snowflake"))
    build_gold_models(engine, Path("sql/snowflake"))
