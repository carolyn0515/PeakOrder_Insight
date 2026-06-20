# 0001. Use Apache Paimon as the Operational Lakehouse State Layer

## Status

Proposed

## Context

The project needs both replayable raw data and frequently updated operational
tables. Plain S3 object storage is excellent for history, but it does not model
row-level updates, deletes, or late-arriving corrections cleanly by itself.

## Decision

Use Apache Paimon for mutable lakehouse tables that represent the latest state of
orders, inventory, demand aggregates, and anomaly signals.

## Consequences

- S3 remains the raw source of truth.
- Paimon becomes the current-state table layer for analytics and processing.
- Serving databases are optional projections, not the primary system of record.
