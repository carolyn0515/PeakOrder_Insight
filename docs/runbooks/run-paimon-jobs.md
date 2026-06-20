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

```bash
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
infra/scripts/submit_emr_serverless_job.sh \
  --application-id YOUR_APPLICATION_ID \
  --execution-role-arn YOUR_PIPELINE_ROLE_ARN \
  --job-name load-order-events \
  --entry-point s3://YOUR_LAKEHOUSE_BUCKET/jobs/load_order_events.py \
  --warehouse s3://YOUR_LAKEHOUSE_BUCKET/paimon \
  --database peakorder_insight_dev \
  --input s3://YOUR_RAW_BUCKET/orders/
```
