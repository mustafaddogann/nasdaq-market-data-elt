from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def test_airflow_dag_imports_when_airflow_is_installed() -> None:
    pytest.importorskip("airflow")
    pytest.importorskip("pandas")
    pytest.importorskip("sqlalchemy")

    dag_path = Path("airflow/dags/nasdaq_market_data_dag.py")
    spec = importlib.util.spec_from_file_location("nasdaq_market_data_dag", dag_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.dag.dag_id == "nasdaq_100_market_data_elt"
    assert [task.task_id for task in module.dag.tasks] == [
        "validate_configuration",
        "run_bronze_silver_gold_elt",
    ]
