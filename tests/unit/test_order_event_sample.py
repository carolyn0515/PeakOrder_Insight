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


def test_sample_order_events_include_peak_traffic_shape() -> None:
    records = [json.loads(line) for line in SAMPLE_PATH.read_text().splitlines() if line.strip()]
    hourly_counts: dict[int, int] = {}

    for record in records:
        hour = int(record["event_time"][11:13])
        hourly_counts[hour] = hourly_counts.get(hour, 0) + 1

    normal_hour_count = hourly_counts[10]
    assert hourly_counts[12] >= normal_hour_count * 5
    assert hourly_counts[13] >= normal_hour_count * 5
    assert hourly_counts[18] >= normal_hour_count * 5
    assert hourly_counts[19] >= normal_hour_count * 5
