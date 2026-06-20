from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "data/schemas/order_event.schema.json"
SAMPLE_PATH = REPO_ROOT / "data/sample/order_events.jsonl"


def test_sample_order_events_match_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = Draft202012Validator(schema)

    records = [json.loads(line) for line in SAMPLE_PATH.read_text().splitlines() if line.strip()]

    assert records, "sample order_events.jsonl should contain at least one event"

    for index, record in enumerate(records, start=1):
        errors = sorted(validator.iter_errors(record), key=lambda error: error.path)
        assert not errors, f"record {index} failed schema validation: {errors}"


def test_sample_order_events_include_late_status_update() -> None:
    records = [json.loads(line) for line in SAMPLE_PATH.read_text().splitlines() if line.strip()]
    order_ids = [record["order_id"] for record in records]

    assert order_ids.count("ord-1001") == 2
    assert {record["event_type"] for record in records if record["order_id"] == "ord-1001"} == {"CREATED", "PAID"}
