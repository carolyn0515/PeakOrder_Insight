# Run the Airflow Paimon DAG

## DAG

`dags/peakorder_paimon_pipeline.py`

The DAG uploads local job assets to S3, bootstraps Apache Paimon tables on EMR
Serverless, then loads sample raw order events into the latest-state tables.

## Runtime Dependencies

Install Airflow runtime dependencies from the project root:

```bash
pip install -r requirements-airflow.txt
```

## Required Environment Variables

```bash
export AWS_REGION=ap-northeast-2
export PROJECT_NAME=peakorder-insight
export ENVIRONMENT=dev
export PEAKORDER_REPO_ROOT=/opt/airflow/PeakOrder_Insight

export LAKEHOUSE_BUCKET=YOUR_LAKEHOUSE_BUCKET
export RAW_BUCKET=YOUR_RAW_BUCKET
export EMR_SERVERLESS_APPLICATION_ID=YOUR_APPLICATION_ID
export PIPELINE_ROLE_ARN=YOUR_PIPELINE_ROLE_ARN
export PAIMON_WAREHOUSE=s3://YOUR_LAKEHOUSE_BUCKET/paimon
export GLUE_DATABASE_NAME=peakorder_insight_dev
```

Optional:

```bash
export PAIMON_SPARK_PACKAGE=org.apache.paimon:paimon-spark-3.5:1.0.1
```

## Flow

```text
upload_assets
  -> bootstrap_tables
  -> load_order_events
```

## Notes

- The DAG uses `boto3` directly to keep provider dependencies small.
- The Airflow worker must be able to read the repository files under
  `PEAKORDER_REPO_ROOT`.
- The Airflow execution role or profile must be allowed to upload to S3 and
  call EMR Serverless APIs.
