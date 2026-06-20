"""Observe Kinesis read latency and write timestamped evidence."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import time
from datetime import UTC, datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read Kinesis records and log publish-to-read latency.")
    parser.add_argument("--stream-name", required=True, help="Kinesis stream name.")
    parser.add_argument("--region", default="ap-northeast-2", help="AWS region.")
    parser.add_argument("--output-csv", default="src/outputs/aws/kinesis_latency.csv", help="Latency evidence CSV.")
    parser.add_argument("--max-records", type=int, default=5000, help="Stop after reading this many records.")
    parser.add_argument("--poll-seconds", type=float, default=1.0, help="Sleep between shard polls.")
    parser.add_argument("--iterator-type", default="LATEST", choices=["LATEST", "TRIM_HORIZON"], help="Shard iterator type.")
    return parser.parse_args()


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def now_utc() -> datetime:
    return datetime.now(UTC)


def open_writer(path: str):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file = output_path.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "read_timestamp_utc",
            "event_hour",
            "records_read",
            "publish_to_read_latency_ms",
            "kinesis_arrival_latency_ms",
            "partition_key",
            "event_id",
        ],
    )
    writer.writeheader()
    return file, writer


def decode_data(data) -> dict[str, object]:
    if isinstance(data, bytes):
        raw = data
    else:
        raw = base64.b64decode(data)
    return json.loads(raw.decode("utf-8"))


def main() -> None:
    args = parse_args()

    import boto3

    client = boto3.client("kinesis", region_name=args.region)
    shards = client.list_shards(StreamName=args.stream_name)["Shards"]
    iterators = {
        shard["ShardId"]: client.get_shard_iterator(
            StreamName=args.stream_name,
            ShardId=shard["ShardId"],
            ShardIteratorType=args.iterator_type,
        )["ShardIterator"]
        for shard in shards
    }

    file, writer = open_writer(args.output_csv)
    records_read = 0

    try:
        while records_read < args.max_records:
            for shard_id, iterator in list(iterators.items()):
                response = client.get_records(ShardIterator=iterator, Limit=1000)
                iterators[shard_id] = response.get("NextShardIterator")
                read_at = now_utc()

                for record in response.get("Records", []):
                    payload = decode_data(record["Data"])
                    published_at = payload.get("_published_at_utc")
                    event_time = str(payload.get("event_time", ""))
                    publish_latency_ms = None

                    if published_at:
                        publish_latency_ms = round((read_at - parse_utc(str(published_at))).total_seconds() * 1000, 2)

                    arrival_latency_ms = round(
                        (read_at - record["ApproximateArrivalTimestamp"].astimezone(UTC)).total_seconds() * 1000,
                        2,
                    )

                    records_read += 1
                    writer.writerow(
                        {
                            "read_timestamp_utc": read_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
                            "event_hour": event_time[11:13] + ":00" if len(event_time) >= 13 else "",
                            "records_read": records_read,
                            "publish_to_read_latency_ms": publish_latency_ms,
                            "kinesis_arrival_latency_ms": arrival_latency_ms,
                            "partition_key": record["PartitionKey"],
                            "event_id": payload.get("event_id", ""),
                        }
                    )

                    if records_read % 500 == 0:
                        print(f"records_read={records_read} latest_publish_latency_ms={publish_latency_ms}", flush=True)

                    if records_read >= args.max_records:
                        break

                file.flush()

            time.sleep(args.poll_seconds)
    finally:
        file.close()


if __name__ == "__main__":
    main()
