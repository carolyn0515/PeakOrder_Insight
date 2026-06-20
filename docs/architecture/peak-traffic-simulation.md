# Peak Traffic Simulation

PeakOrder Insight models an operational ordering system where traffic is mostly
stable, then spikes sharply during lunch and dinner windows.

## Traffic Shape

The sample generator creates deterministic JSONL order events with this hourly
shape:

- Overnight hours: very low traffic.
- Normal daytime hours: baseline traffic.
- 11:00, 17:00, 20:00: pre/post-peak shoulder traffic.
- 12:00, 13:00, 18:00, 19:00: peak traffic.

Default generation parameters:

```bash
python3 src/ingestion/generate_peak_order_events.py \
  --base-orders-per-hour 5000 \
  --peak-multiplier 10
```

This produces 50,000 orders per peak hour, 5,000 orders per normal daytime hour, and 281,660 total events for the sample business day.

## Detection Logic

The peak detection job reads `order_items_latest` from Paimon and writes:

- `store_order_pressure_hourly`
- `peak_order_alerts`

For each store-hour, it calculates:

```text
pressure_ratio = hourly_order_count / average_hourly_order_count_for_store
```

An alert is emitted when:

```text
order_count >= PEAK_MIN_ORDERS
pressure_ratio >= PEAK_PRESSURE_THRESHOLD
```

## Why This Matters

This makes the project's core scenario explicit: the platform is not just moving
orders into a lakehouse, it is detecting operational pressure caused by
time-localized demand spikes.
