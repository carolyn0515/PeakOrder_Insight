from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DAG_PATH = REPO_ROOT / "dags/peakorder_paimon_pipeline.py"


def test_airflow_dag_imports() -> None:
    spec = importlib.util.spec_from_file_location("peakorder_paimon_pipeline", DAG_PATH)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module, "peakorder_paimon_pipeline")
