"""Publish generated order events to Amazon Kinesis in timed batches."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish order events JSONL to Kinesis.")
    parser.add_argument("--input", default="data/sample/order_events.jsonl", help="Input order events JSONL.")
    parser.add_argument("--stream-name", required=True, help="Kinesis stream name.")
    parser.add_argument("--region", default="ap-northeast-2", help="AWS region.")
    parser.add_argument("--batch-size", type=int, default=500, help="Records per PutRecords call.")
    parser.add_argument("--sleep-ms", type=int, default=100, help="Sleep between batches in milliseconds.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of records to publish.")
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


def main() -> None:
    args = parse_args()

    import boto3

    client = boto3.client("kinesis", region_name=args.region)
    records = load_records(Path(args.input), args.limit)
    published = 0

    for batch in chunks(records, args.batch_size):
        response = client.put_records(
            StreamName=args.stream_name,
            Records=[
                {
                    "Data": json.dumps(record, separators=(",", ":")).encode("utf-8"),
                    "PartitionKey": str(record["store_id"]),
                }
                for record in batch
            ],
        )
        failed = response.get("FailedRecordCount", 0)
        if failed:
            raise RuntimeError(f"Kinesis PutRecords failed for {failed} records")

        published += len(batch)
        print(f"published_records={published}")
        time.sleep(args.sleep_ms / 1000)


if __name__ == "__main__":
    main()
