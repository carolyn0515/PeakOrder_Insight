"""Local real-time dashboard API for portfolio demos.

This server replays generated order events in batches and exposes a live
dashboard JSON endpoint. It lets the frontend behave like a real-time operating
console before deploying the AWS Kinesis path.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


class LiveState:
    def __init__(self, events: list[dict[str, object]], batch_size: int, interval_seconds: float):
        self.events = events
        self.batch_size = batch_size
        self.interval_seconds = interval_seconds
        self.index = 0
        self.lock = threading.Lock()
        self.hourly_counts: Counter[int] = Counter()
        self.store_hour_counts: dict[str, Counter[int]] = defaultdict(Counter)
        self.store_counts: Counter[str] = Counter()
        self.product_units: Counter[str] = Counter()
        self.product_sales: Counter[str] = Counter()
        self.total_sales = 0
        self.started_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    def event_hour(self, event: dict[str, object]) -> int:
        return datetime.fromisoformat(str(event["event_time"]).replace("Z", "+00:00")).hour

    def apply_event(self, event: dict[str, object]) -> None:
        hour = self.event_hour(event)
        store_id = str(event["store_id"])
        self.hourly_counts[hour] += 1
        self.store_hour_counts[store_id][hour] += 1
        self.store_counts[store_id] += 1

        for item in event.get("items", []):
            product_id = str(item["product_id"])
            quantity = int(item["quantity"])
            unit_price = int(item["unit_price"])
            self.product_units[product_id] += quantity
            self.product_sales[product_id] += quantity * unit_price
            self.total_sales += quantity * unit_price

    def tick(self) -> None:
        while self.index < len(self.events):
            with self.lock:
                next_index = min(self.index + self.batch_size, len(self.events))
                for event in self.events[self.index : next_index]:
                    self.apply_event(event)
                self.index = next_index
            time.sleep(self.interval_seconds)

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            hourly = [{"hour": f"{hour:02d}:00", "orders": self.hourly_counts[hour]} for hour in range(24)]
            pressure_rows = []
            alerts = []

            for store_id, counts in sorted(self.store_hour_counts.items()):
                baseline = max(1, sum(counts.values()) / 24)
                for hour in range(24):
                    orders = counts[hour]
                    pressure_ratio = orders / baseline
                    row = {
                        "store_id": store_id,
                        "hour": f"{hour:02d}:00",
                        "orders": orders,
                        "baseline_orders": round(baseline, 2),
                        "pressure_ratio": round(pressure_ratio, 2),
                    }
                    pressure_rows.append(row)
                    if orders >= 20 and pressure_ratio >= 2.5:
                        alerts.append(
                            {
                                **row,
                                "severity": "CRITICAL" if pressure_ratio >= 3.75 else "WARNING",
                            }
                        )

            top_products = [
                {
                    "product_id": product_id,
                    "units_sold": self.product_units[product_id],
                    "gross_sales": self.product_sales[product_id],
                }
                for product_id, _ in self.product_units.most_common(8)
            ]

            processed = self.index
            peak_orders = sum(self.hourly_counts[hour] for hour in [12, 13, 18, 19])
            return {
                "live": {
                    "mode": "local-replay",
                    "started_at": self.started_at,
                    "processed_events": processed,
                    "total_source_events": len(self.events),
                    "progress": round(processed / len(self.events), 4) if self.events else 0,
                },
                "summary": {
                    "total_orders": processed,
                    "peak_orders": peak_orders,
                    "total_sales": self.total_sales,
                    "alert_count": len(alerts),
                    "store_count": len(self.store_counts),
                },
                "hourly_orders": hourly,
                "store_pressure": pressure_rows,
                "alerts": sorted(alerts, key=lambda item: (-float(item["pressure_ratio"]), item["store_id"], item["hour"]))[:12],
                "top_products": top_products,
                "store_totals": [{"store_id": store, "orders": count} for store, count in self.store_counts.most_common()],
            }


def load_events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def make_handler(state: LiveState):
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/live-dashboard":
                payload = json.dumps(state.snapshot()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            if parsed.path == "/api/health":
                payload = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            super().do_GET()

    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve live dashboard replay API.")
    parser.add_argument("--events", default="data/sample/order_events.jsonl", help="Order event JSONL path.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8010, help="Bind port.")
    parser.add_argument("--batch-size", type=int, default=2500, help="Events applied per tick.")
    parser.add_argument("--interval-seconds", type=float, default=1.0, help="Seconds between ticks.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state = LiveState(load_events(Path(args.events)), args.batch_size, args.interval_seconds)
    thread = threading.Thread(target=state.tick, daemon=True)
    thread.start()

    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    print(f"live_dashboard=http://{args.host}:{args.port}/frontend/")
    print(f"live_api=http://{args.host}:{args.port}/api/live-dashboard")
    server.serve_forever()


if __name__ == "__main__":
    main()
