# Architecture Overview

## Goal

Build an AWS-based order insight platform that keeps raw event history and a
fresh operational state for analytics and downstream serving.

## Data Flow

```text
Order events
  -> S3 raw zone
  -> validation and normalization
  -> Apache Paimon lakehouse tables
  -> analytics and serving projections
```

## Layer Responsibilities

- `S3`: append-only source of truth and replayable history.
- `Apache Paimon`: latest mutable lakehouse state with upsert/delete semantics.
- `Glue/Athena/EMR/Flink`: catalog, query, batch, and streaming compute.
- `Serving stores`: low-latency API, dashboard, or search projections.

## Initial Tables

- `orders_latest`
- `order_items_latest`
- `product_demand_daily`
- `store_inventory_latest`
- `order_anomaly_events`
