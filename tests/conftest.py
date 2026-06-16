from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture()
def alpha_vantage_daily_payload(fixture_dir: Path) -> dict:
    return json.loads((fixture_dir / "alpha_vantage_daily_aapl.json").read_text(encoding="utf-8"))
