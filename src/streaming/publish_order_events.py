"""Publish generated order events to Amazon Kinesis in timed batches."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish order events JSONL to Kinesis.")
    parser.add_argument("--input", default="data/sample/order_events.jsonl", help="Input order events JSONL.")
    parser.add_argument("--stream-name", required=True, help="Kinesis stream name.")
    parser.add_argument("--region", default="ap-northeast-2", help="AWS region.")
    parser.add_argument("--batch-size", type=int, default=500, help="Records per PutRecords call.")
    parser.add_argument("--sleep-ms", type=int, default=100, help="Sleep between batches in milliseconds.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of records to publish.")
    parser.add_argument(
        "--mode",
        choices=["fixed", "peak-shaped"],
        default="fixed",
        help="fixed uses a constant sleep; peak-shaped replays each event hour over a fixed wall-clock window.",
    )
    parser.add_argument(
        "--simulated-hour-seconds",
        type=float,
        default=30.0,
        help="Wall-clock seconds used to replay one event_time hour in peak-shaped mode.",
    )
    parser.add_argument("--progress-csv", default="", help="Optional CSV path for timestamped publish progress.")
    return parser.parse_args()


def chunks(records: list[dict[str, object]], size: int):
    for index in range(0, len(records), size):
        yield records[index : index + size]


def load_records(path: Path, limit: int) -> list[dict[str, object]]:
    records = []
    with path.open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                records.append(json.loads(line))
            if limit and len(records) >= limit:
                break
    return records


def event_hour(record: dict[str, object]) -> int:
    return datetime.fromisoformat(str(record["event_time"]).replace("Z", "+00:00")).hour


def timestamp_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def open_progress_writer(path: str):
    if not path:
        return None, None

    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_file = csv_path.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        csv_file,
        fieldnames=[
            "timestamp_utc",
            "elapsed_seconds",
            "event_hour",
            "batch_records",
            "published_records",
            "records_per_second",
            "failed_records",
        ],
    )
    writer.writeheader()
    return csv_file, writer


def publish_batch(client, stream_name: str, batch: list[dict[str, object]]) -> int:
    response = client.put_records(
        StreamName=stream_name,
        Records=[
            {
                "Data": json.dumps(
                    {
                        **record,
                        "_published_at_utc": timestamp_utc(),
                    },
                    separators=(",", ":"),
                ).encode("utf-8"),
                "PartitionKey": str(record["store_id"]),
            }
            for record in batch
        ],
    )
    return int(response.get("FailedRecordCount", 0))


def write_progress(writer, csv_file, started: float, event_hour_value: str, batch_size: int, published: int, failed: int) -> None:
    elapsed = max(time.monotonic() - started, 0.001)
    records_per_second = published / elapsed
    now = timestamp_utc()

    if writer:
        writer.writerow(
            {
                "timestamp_utc": now,
                "elapsed_seconds": round(elapsed, 3),
                "event_hour": event_hour_value,
                "batch_records": batch_size,
                "published_records": published,
                "records_per_second": round(records_per_second, 2),
                "failed_records": failed,
            }
        )
        csv_file.flush()

    print(
        f"timestamp_utc={now} event_hour={event_hour_value} "
        f"published_records={published} batch_records={batch_size} "
        f"records_per_second={records_per_second:.2f}",
        flush=True,
    )


def grouped_by_event_hour(records: list[dict[str, object]]) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        grouped[event_hour(record)].append(record)
    return dict(sorted(grouped.items()))


def main() -> None:
    args = parse_args()

    import boto3

    client = boto3.client("kinesis", region_name=args.region)
    records = load_records(Path(args.input), args.limit)
    published = 0
    started = time.monotonic()
    csv_file, writer = open_progress_writer(args.progress_csv)

    try:
        if args.mode == "peak-shaped":
            for hour, hour_records in grouped_by_event_hour(records).items():
                hour_batches = list(chunks(hour_records, args.batch_size))
                sleep_seconds = args.simulated_hour_seconds / max(len(hour_batches), 1)

                for batch in hour_batches:
                    failed = publish_batch(client, args.stream_name, batch)
                    if failed:
                        raise RuntimeError(f"Kinesis PutRecords failed for {failed} records")

                    published += len(batch)
                    write_progress(writer, csv_file, started, f"{hour:02d}:00", len(batch), published, failed)
                    time.sleep(sleep_seconds)
        else:
            for batch in chunks(records, args.batch_size):
                failed = publish_batch(client, args.stream_name, batch)
                if failed:
                    raise RuntimeError(f"Kinesis PutRecords failed for {failed} records")

                published += len(batch)
                write_progress(writer, csv_file, started, "mixed", len(batch), published, failed)
                time.sleep(args.sleep_ms / 1000)
    finally:
        if csv_file:
            csv_file.close()


if __name__ == "__main__":
    main()
