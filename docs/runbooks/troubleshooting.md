# Troubleshooting Notes

This project intentionally includes operational failure points that are useful
for a portfolio report: malformed events, skewed peak traffic, late updates,
Paimon merge behavior, EMR Serverless packaging, and Airflow orchestration.

## 1. Order Event Quality Gate Fails

Symptoms:

- Airflow stops at `validate_order_events`.
- EMR Serverless logs show `Order event quality check failed`.

Likely causes:

- Missing `event_id`, `order_id`, `event_type`, or `event_time`.
- `event_time` is not parseable as a timestamp.
- Empty `items` array.
- Item quantity is zero or negative.
- Item price is negative.

Resolution:

- Inspect the raw JSONL object under `s3://RAW_BUCKET/orders/`.
- Re-run `src/ingestion/generate_peak_order_events.py` for a known-good sample.
- Keep the quality gate before Paimon writes so invalid records never reach the
  latest-state tables.

## 2. Peak Detection Does Not Produce Alerts

Symptoms:

- `store_order_pressure_hourly` has rows.
- `peak_order_alerts` is empty.

Likely causes:

- `PEAK_PRESSURE_THRESHOLD` is too high.
- `PEAK_MIN_ORDERS` is higher than generated hourly peak volume.
- Input data does not include lunch or dinner spikes.

Resolution:

- Lower `PEAK_PRESSURE_THRESHOLD`, for example from `2.5` to `1.8`.
- Lower `PEAK_MIN_ORDERS` for small demo datasets.
- Generate a stronger sample:

```bash
python3 src/ingestion/generate_peak_order_events.py \
  --base-orders-per-hour 8 \
  --peak-multiplier 7
```

## 3. Paimon Merge Results Look Too Small

Symptoms:

- Raw JSONL has many events.
- `orders_latest` only has one row per `order_id`.

Explanation:

This is expected. `orders_latest` and `order_items_latest` are latest-state
tables, not append-only event history. The pipeline keeps mutable state in
Paimon, while raw events remain replayable in S3.

Resolution:

- Use S3 raw data for event-history replay.
- Use `store_order_pressure_hourly` and `peak_order_alerts` for peak-time
  operational insight.

## 4. EMR Serverless Job Cannot Resolve Paimon Classes

Symptoms:

- Job fails with `ClassNotFoundException` for Paimon Spark catalog classes.

Likely causes:

- `PAIMON_SPARK_PACKAGE` does not match the EMR Spark runtime.
- Maven package resolution is blocked by network configuration.

Resolution:

- Check `PAIMON_SPARK_PACKAGE`.
- Package and upload the Paimon jar to S3 if the runtime cannot download Maven
  dependencies.
- Keep the package value visible in `configs/dev/pipeline.yaml` and
  `.env.example` for reproducibility.

## 5. Airflow DAG Parses But Job Submission Fails

Symptoms:

- DAG appears in Airflow.
- Tasks fail at EMR Serverless API calls.

Likely causes:

- Missing `EMR_SERVERLESS_APPLICATION_ID`.
- Missing or incorrect `PIPELINE_ROLE_ARN`.
- Airflow worker AWS credentials cannot call S3 or EMR Serverless.

Resolution:

- Compare Airflow environment variables with `docs/runbooks/run-airflow-dag.md`.
- Confirm the pipeline IAM role trusts `emr-serverless.amazonaws.com`.
- Confirm S3 bucket permissions include both script upload and raw event upload.
