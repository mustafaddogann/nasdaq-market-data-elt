"""Airflow DAG for Nasdaq-100 daily market data ELT."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Union

from airflow import DAG
from airflow.operators.python import PythonOperator

from nasdaq_elt.config import load_settings
from nasdaq_elt.db import build_snowflake_connection_kwargs
from nasdaq_elt.pipeline import run_pipeline
from nasdaq_elt.transform import load_symbol_universe


def validate_configuration() -> Dict[str, Union[str, int]]:
    settings = load_settings()
    if not settings.alpha_vantage_api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY must be set before running live ingestion.")
    build_snowflake_connection_kwargs(settings)

    symbols = load_symbol_universe(settings.symbols_path, settings.nasdaq_symbol_limit)
    return {
        "symbol_count": len(symbols),
        "load_start_date": settings.load_start_date.isoformat(),
        "outputsize": settings.alpha_vantage_outputsize,
    }


with DAG(
    dag_id="nasdaq_100_market_data_elt",
    description="Ingest Alpha Vantage daily OHLCV data for a Nasdaq-100 ticker universe.",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["portfolio", "nasdaq-100", "snowflake", "elt"],
) as dag:
    validate_config = PythonOperator(
        task_id="validate_configuration",
        python_callable=validate_configuration,
    )

    run_elt = PythonOperator(
        task_id="run_bronze_silver_gold_elt",
        python_callable=run_pipeline,
    )

    validate_config >> run_elt
