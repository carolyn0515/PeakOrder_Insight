"""Generate synthetic order events with lunch and dinner peak traffic."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class Product:
    product_id: str
    unit_price: int
    weight: int


PRODUCTS = [
    Product("americano", 4500, 24),
    Product("latte", 5200, 18),
    Product("cold_brew", 5600, 12),
    Product("bagel", 3800, 10),
    Product("sandwich", 7200, 8),
    Product("salad", 6800, 5),
]

STORES = ["store-gangnam", "store-hongdae", "store-jamsil", "store-yeouido"]
PEAK_HOURS = {12, 13, 18, 19}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate peak-skewed order event JSONL.")
    parser.add_argument("--output", default="data/sample/order_events.jsonl", help="Output JSONL path.")
    parser.add_argument("--date", default="2026-06-20", help="Business date in YYYY-MM-DD.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic samples.")
    parser.add_argument("--base-orders-per-hour", type=int, default=1000, help="Average normal hourly order volume.")
    parser.add_argument("--peak-multiplier", type=int, default=8, help="Multiplier applied during peak hours.")
    return parser.parse_args()


def choose_items(rng: random.Random) -> list[dict[str, int | str]]:
    product_count = rng.choices([1, 2, 3], weights=[65, 28, 7], k=1)[0]
    products = rng.choices(PRODUCTS, weights=[product.weight for product in PRODUCTS], k=product_count)

    return [
        {
            "product_id": product.product_id,
            "quantity": rng.choices([1, 2, 3], weights=[72, 23, 5], k=1)[0],
            "unit_price": product.unit_price,
        }
        for product in products
    ]


def hourly_volume(hour: int, base_orders_per_hour: int, peak_multiplier: int) -> int:
    if hour in PEAK_HOURS:
        return base_orders_per_hour * peak_multiplier
    if hour in {11, 17, 20}:
        return base_orders_per_hour * 2
    if hour < 8 or hour > 21:
        return max(1, base_orders_per_hour // 3)
    return base_orders_per_hour


def generate_events(args: argparse.Namespace) -> list[dict[str, object]]:
    rng = random.Random(args.seed)
    business_day = datetime.fromisoformat(args.date).replace(tzinfo=timezone.utc)
    events: list[dict[str, object]] = []
    sequence = 1

    for hour in range(24):
        volume = hourly_volume(hour, args.base_orders_per_hour, args.peak_multiplier)
        for _ in range(volume):
            minute = rng.randint(0, 59)
            second = rng.randint(0, 59)
            event_time = business_day + timedelta(hours=hour, minutes=minute, seconds=second)
            store_id = rng.choices(STORES, weights=[36, 28, 20, 16], k=1)[0]
            order_id = f"ord-{sequence:06d}"

            events.append(
                {
                    "event_id": f"evt-{sequence:06d}",
                    "order_id": order_id,
                    "customer_id": f"cus-{rng.randint(1, 350):04d}",
                    "store_id": store_id,
                    "event_type": "PAID",
                    "event_time": event_time.isoformat().replace("+00:00", "Z"),
                    "items": choose_items(rng),
                }
            )
            sequence += 1

    events.sort(key=lambda event: str(event["event_time"]))
    return events


def main() -> None:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    events = generate_events(args)
    with output_path.open("w", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event, separators=(",", ":")) + "\n")

    peak_count = sum(1 for event in events if datetime.fromisoformat(str(event["event_time"]).replace("Z", "+00:00")).hour in PEAK_HOURS)
    print(f"generated_events={len(events)}")
    print(f"peak_events={peak_count}")
    print(f"output={output_path}")


if __name__ == "__main__":
    main()
