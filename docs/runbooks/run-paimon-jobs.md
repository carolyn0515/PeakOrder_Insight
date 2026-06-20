# Run Paimon Jobs on EMR Serverless

## Prerequisites

- Terraform dev environment has been applied.
- Job scripts have been uploaded to S3.
- AWS CLI and `jq` are available locally.

## 1. Read Terraform Outputs

```bash
cd infra/terraform/envs/dev
terraform output
```

Required values:

- `emr_serverless_application_id`
- `pipeline_role_arn`
- `paimon_warehouse_uri`
- `glue_database_name`
- `raw_bucket_name`

## 2. Upload Job Scripts and Sample Events

```bash
infra/scripts/upload_job_assets.sh \
  --lakehouse-bucket YOUR_LAKEHOUSE_BUCKET \
  --raw-bucket YOUR_RAW_BUCKET
```

## 3. Bootstrap Tables

For private subnets without Maven Central access, upload the Paimon runtime jar
to S3 first and pass it through `PAIMON_SPARK_JAR_URI`.

```bash
PAIMON_SPARK_JAR_URI=s3://YOUR_LAKEHOUSE_BUCKET/jars/paimon-spark-3.5-1.0.1.jar \
infra/scripts/submit_emr_serverless_job.sh \
  --application-id YOUR_APPLICATION_ID \
  --execution-role-arn YOUR_PIPELINE_ROLE_ARN \
  --job-name bootstrap-paimon-tables \
  --entry-point s3://YOUR_LAKEHOUSE_BUCKET/jobs/bootstrap_tables.py \
  --warehouse s3://YOUR_LAKEHOUSE_BUCKET/paimon \
  --database peakorder_insight_dev
```

## 4. Load Raw Order Events

```bash
PAIMON_SPARK_JAR_URI=s3://YOUR_LAKEHOUSE_BUCKET/jars/paimon-spark-3.5-1.0.1.jar \
infra/scripts/submit_emr_serverless_job.sh \
  --application-id YOUR_APPLICATION_ID \
  --execution-role-arn YOUR_PIPELINE_ROLE_ARN \
  --job-name load-order-events \
  --entry-point s3://YOUR_LAKEHOUSE_BUCKET/jobs/load_order_events.py \
  --warehouse s3://YOUR_LAKEHOUSE_BUCKET/paimon \
  --database peakorder_insight_dev \
  --input s3://YOUR_RAW_BUCKET/orders/
```

## 5. Detect Peak Pressure In Paimon

```bash
PAIMON_SPARK_JAR_URI=s3://YOUR_LAKEHOUSE_BUCKET/jars/paimon-spark-3.5-1.0.1.jar \
infra/scripts/submit_emr_serverless_job.sh \
  --application-id YOUR_APPLICATION_ID \
  --execution-role-arn YOUR_PIPELINE_ROLE_ARN \
  --job-name detect-peak-pressure \
  --entry-point s3://YOUR_LAKEHOUSE_BUCKET/jobs/detect_peak_pressure.py \
  --warehouse s3://YOUR_LAKEHOUSE_BUCKET/paimon \
  --database peakorder_insight_dev
```

## 6. Materialize Lakehouse Evidence Without Paimon Runtime

If the EMR job cannot download the Paimon runtime package from Maven because
the application runs in private subnets, use the dependency-light Spark job
below to create report-ready JSON and Parquet exports first.

```bash
aws emr-serverless start-job-run \
  --region ap-northeast-2 \
  --application-id YOUR_APPLICATION_ID \
  --execution-role-arn YOUR_PIPELINE_ROLE_ARN \
  --name materialize-lakehouse-views-small-executor \
  --job-driver '{
    "sparkSubmit": {
      "entryPoint": "s3://YOUR_LAKEHOUSE_BUCKET/jobs/materialize_lakehouse_views.py",
      "entryPointArguments": [
        "--input", "s3://YOUR_RAW_BUCKET/orders/",
        "--output", "s3://YOUR_LAKEHOUSE_BUCKET/exports",
        "--peak-threshold", "1.8",
        "--min-orders", "100"
      ],
      "sparkSubmitParameters": "--conf spark.dynamicAllocation.enabled=false --conf spark.executor.instances=1 --conf spark.executor.cores=1 --conf spark.executor.memory=2g --conf spark.driver.cores=1 --conf spark.driver.memory=2g"
    }
  }' \
  --configuration-overrides '{"monitoringConfiguration":{"cloudWatchLoggingConfiguration":{"enabled":true}}}'
```

Expected CloudWatch stdout evidence:

```text
materialized_raw_event_rows=281660
materialized_order_item_rows=399846
materialized_product_demand_rows=24
materialized_pressure_rows=96
materialized_alert_rows=16
```
