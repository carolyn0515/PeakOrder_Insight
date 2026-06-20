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

## 6. EMR Serverless Job Fails To Push CloudWatch Logs

Symptoms:

- EMR Serverless application starts in private subnets.
- A Spark job moves from `PENDING` to `SCHEDULED` or `RUNNING`, then fails.
- Job details show a message similar to:
  `Unable to push logs... Connect timeout on endpoint URL: https://logs.ap-northeast-2.amazonaws.com/`.

Likely cause:

- The EMR Serverless job runs inside private subnets with no NAT gateway.
- The VPC has an S3 gateway endpoint, but it does not have a CloudWatch Logs
  interface endpoint.
- S3 reads can work while log delivery to CloudWatch Logs still times out.

Resolution:

- Add a CloudWatch Logs interface VPC endpoint:
  `com.amazonaws.ap-northeast-2.logs`.
- Enable private DNS on the endpoint.
- Attach a security group that allows HTTPS from the project VPC CIDR.
- Confirm the EMR execution role can call CloudWatch Logs APIs:
  `logs:DescribeLogGroups`, `logs:DescribeLogStreams`,
  `logs:CreateLogGroup`, `logs:CreateLogStream`, and `logs:PutLogEvents`.
- Re-run the EMR Serverless validation job and confirm log delivery.

Report angle:

- This is a useful troubleshooting case because the original private-subnet
  design was directionally correct for data access, but incomplete for
  operational observability.

## 7. EMR Serverless Job Exceeds Application Maximum Capacity

Symptoms:

- CloudWatch Logs are delivered successfully.
- Spark driver logs show:
  `ApplicationMaxCapacityExceededException`.
- The job keeps retrying executor allocation instead of finishing quickly.

Likely cause:

- Spark dynamic allocation requested more executors than the demo EMR
  Serverless application can run.
- For example, the application maximum is `8 vCPU / 24 GB`, but Spark attempts
  to launch multiple executors with the default EMR runtime sizing.

Resolution:

- For validation or small portfolio evidence jobs, disable dynamic allocation.
- Run with one small executor:
  `spark.dynamicAllocation.enabled=false`,
  `spark.executor.instances=1`,
  `spark.executor.cores=1`,
  `spark.executor.memory=2g`,
  `spark.driver.cores=1`, and
  `spark.driver.memory=2g`.

Report angle:

- This is a realistic right-sizing issue: the pipeline does not need large
  executor fan-out for a small raw-data validation step, while peak ingestion
  pressure is already demonstrated in Kinesis.

## 8. Paimon Bootstrap Hangs While Resolving Maven Packages

Symptoms:

- EMR Serverless job stays `RUNNING` for several minutes.
- Driver logs show Ivy dependency resolution for
  `org.apache.paimon:paimon-spark-3.5`.
- No Paimon table files appear under the warehouse prefix.

Likely cause:

- The application runs in private subnets without NAT.
- The S3 and CloudWatch Logs endpoints are enough for S3/log traffic, but they
  do not provide Maven Central access.

Resolution:

- For the final Paimon path, package the Paimon runtime jar and upload it to S3,
  then submit Spark with `--jars s3://.../paimon-spark-3.5.jar`.
- Alternatively add controlled NAT egress for dependency resolution.
- For report evidence while packaging is pending, run
  `src/serving/materialize_lakehouse_views.py`, which uses only built-in Spark
  readers/writers and writes Parquet/JSON exports to the lakehouse bucket.

Observed evidence:

- `bootstrap-paimon-tables-small-executor` was cancelled after it stayed in
  Maven package resolution.
- `materialize-lakehouse-views-small-executor` completed successfully and
  produced `281660` raw event rows, `399846` item rows, `96` hourly pressure
  rows, and `16` peak alert rows.
