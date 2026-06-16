"""End-to-end ELT orchestration logic used by Airflow and local runs."""

from __future__ import annotations

import logging
import time
from typing import Optional

import pandas as pd

from nasdaq_elt.alpha_vantage import AlphaVantageClient
from nasdaq_elt.config import Settings, load_settings
from nasdaq_elt.db import (
    build_gold_models,
    initialize_database,
    insert_raw_api_response,
    make_engine,
    upsert_daily_prices,
    upsert_securities,
    upsert_trading_calendar,
)
from nasdaq_elt.quality import validate_price_frame
from nasdaq_elt.transform import (
    build_trading_calendar,
    filter_prices_from_start,
    load_symbol_universe,
    parse_daily_prices,
)

logger = logging.getLogger(__name__)


def run_pipeline(settings: Optional[Settings] = None) -> dict[str, int]:
    settings = settings or load_settings()
    engine = make_engine(settings)
    client = AlphaVantageClient(
        api_key=settings.alpha_vantage_api_key,
        base_url=settings.alpha_vantage_base_url,
        timeout_seconds=settings.alpha_vantage_timeout_seconds,
    )

    initialize_database(engine, settings.sql_path)
    securities = load_symbol_universe(settings.symbols_path, settings.nasdaq_symbol_limit)
    upsert_securities(engine, securities)

    loaded_prices: list[pd.DataFrame] = []
    for symbol in securities["symbol"].tolist():
        logger.info("Fetching daily prices for %s", symbol)
        api_response = client.fetch_daily_prices(
            symbol=symbol,
            outputsize=settings.alpha_vantage_outputsize,
        )
        raw_response_id = insert_raw_api_response(
            engine=engine,
            symbol=symbol,
            request_params=api_response.request_params,
            response_payload=api_response.payload,
            status_code=api_response.status_code,
            api_message=api_response.api_message,
        )
        prices = parse_daily_prices(symbol=symbol, payload=api_response.payload)
        prices = filter_prices_from_start(prices, settings.load_start_date)
        validate_price_frame(prices, settings.load_start_date)
        upsert_daily_prices(engine, prices, raw_response_id=raw_response_id)
        loaded_prices.append(prices)
        time.sleep(settings.alpha_vantage_api_pause_seconds)

    all_prices = pd.concat(loaded_prices, ignore_index=True) if loaded_prices else pd.DataFrame()
    upsert_trading_calendar(engine, build_trading_calendar(all_prices))
    build_gold_models(engine, settings.sql_path)

    return {
        "symbols_loaded": int(len(securities)),
        "price_rows_loaded": int(len(all_prices)),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    result = run_pipeline()
    logger.info("Pipeline complete: %s", result)


if __name__ == "__main__":
    main()
