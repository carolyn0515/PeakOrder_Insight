"""Build static dashboard sample data from generated order events."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build frontend dashboard sample JSON.")
    parser.add_argument("--input", default="data/sample/order_events.jsonl", help="Input order events JSONL.")
    parser.add_argument("--output", default="frontend/data/dashboard.json", help="Output dashboard JSON.")
    parser.add_argument("--threshold", type=float, default=2.5, help="Peak pressure alert threshold.")
    parser.add_argument("--min-orders", type=int, default=20, help="Minimum hourly orders for alerts.")
    return parser.parse_args()


def load_events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def event_hour(event: dict[str, object]) -> int:
    return datetime.fromisoformat(str(event["event_time"]).replace("Z", "+00:00")).hour


def build_dashboard(events: list[dict[str, object]], threshold: float, min_orders: int) -> dict[str, object]:
    hourly_counts: Counter[int] = Counter()
    store_hour_counts: dict[str, Counter[int]] = defaultdict(Counter)
    store_counts: Counter[str] = Counter()
    product_units: Counter[str] = Counter()
    product_sales: Counter[str] = Counter()
    total_sales = 0

    for event in events:
        hour = event_hour(event)
        store_id = str(event["store_id"])
        hourly_counts[hour] += 1
        store_hour_counts[store_id][hour] += 1
        store_counts[store_id] += 1

        for item in event.get("items", []):
            product_id = str(item["product_id"])
            quantity = int(item["quantity"])
            unit_price = int(item["unit_price"])
            line_total = quantity * unit_price
            product_units[product_id] += quantity
            product_sales[product_id] += line_total
            total_sales += line_total

    hourly = [{"hour": f"{hour:02d}:00", "orders": hourly_counts[hour]} for hour in range(24)]

    pressure_rows = []
    alerts = []
    for store_id, counts in sorted(store_hour_counts.items()):
        baseline = sum(counts.values()) / 24
        for hour in range(24):
            order_count = counts[hour]
            pressure_ratio = 0 if baseline == 0 else order_count / baseline
            row = {
                "store_id": store_id,
                "hour": f"{hour:02d}:00",
                "orders": order_count,
                "baseline_orders": round(baseline, 2),
                "pressure_ratio": round(pressure_ratio, 2),
            }
            pressure_rows.append(row)
            if order_count >= min_orders and pressure_ratio >= threshold:
                alerts.append(
                    {
                        **row,
                        "severity": "CRITICAL" if pressure_ratio >= threshold * 1.5 else "WARNING",
                    }
                )

    top_products = [
        {
            "product_id": product_id,
            "units_sold": product_units[product_id],
            "gross_sales": product_sales[product_id],
        }
        for product_id, _ in product_units.most_common(8)
    ]

    return {
        "summary": {
            "total_orders": len(events),
            "peak_orders": sum(hourly_counts[hour] for hour in [12, 13, 18, 19]),
            "total_sales": total_sales,
            "alert_count": len(alerts),
            "store_count": len(store_counts),
        },
        "hourly_orders": hourly,
        "store_pressure": pressure_rows,
        "alerts": sorted(alerts, key=lambda item: (-float(item["pressure_ratio"]), item["store_id"], item["hour"]))[:12],
        "top_products": top_products,
        "store_totals": [{"store_id": store, "orders": count} for store, count in store_counts.most_common()],
    }


def main() -> None:
    args = parse_args()
    events = load_events(Path(args.input))
    dashboard = build_dashboard(events, args.threshold, args.min_orders)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
    print(f"dashboard_sample={output}")
    print(f"total_orders={dashboard['summary']['total_orders']}")


if __name__ == "__main__":
    main()
