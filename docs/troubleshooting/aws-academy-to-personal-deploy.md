# AWS Academy to Personal Account Deployment

## Context

PeakOrder Insight was first tested with AWS Academy credentials, then deployed
with a personal AWS account after Academy permissions blocked the infrastructure
bootstrap.

## AWS Academy Result

`terraform plan` succeeded, but `terraform apply` failed because the lab role did
not allow core infrastructure actions:

- `iam:CreateRole`
- `ec2:CreateVpc`
- `s3:CreateBucket`
- `glue:CreateSecurityConfiguration`
- `logs:CreateLogGroup`
- `SNS:CreateTopic`
- `kinesis:AddTagsToStream`

This confirmed that AWS Academy was too restricted for a Terraform-managed
streaming lakehouse stack.

## Personal Account Deployment Result

The same Terraform stack was applied successfully in the personal AWS account.

```text
Apply complete! Resources: 31 added, 0 changed, 0 destroyed.
```

Created resources included:

- VPC, private subnets, route table, and S3 VPC endpoint
- Raw and lakehouse S3 buckets
- Glue catalog database and security configuration
- EMR Serverless Spark application
- Kinesis Data Stream for order events
- IAM pipeline role and policy
- CloudWatch log group and SNS alert topic

## Verified Outputs

```text
order_events_stream_name = peakorder-insight-dev-order-events
raw_bucket_name          = peakorder-insight-dev-raw-87d26f49
lakehouse_bucket_name    = peakorder-insight-dev-lakehouse-87d26f49
glue_database_name       = peakorder_insight_dev
emr_application_id       = 00g6jdr757uarv2p
```

Kinesis stream verification:

```text
StreamStatus: ACTIVE
OpenShardCount: 2
RetentionPeriodHours: 24
EncryptionType: KMS
```

EMR Serverless verification:

```text
state: CREATED
releaseLabel: emr-7.2.0
type: Spark
maximumCapacity: 8 vCPU, 24 GB, 100 GB
```

## Streaming Smoke Test

Published 1,000 generated order events to Kinesis:

```bash
python3 src/streaming/publish_order_events.py \
  --stream-name peakorder-insight-dev-order-events \
  --region ap-northeast-2 \
  --batch-size 500 \
  --sleep-ms 100 \
  --limit 1000
```

Producer output:

```text
published_records=500
published_records=1000
```

Readback from Kinesis returned order-event payloads with partition keys such as
`store-gangnam`, proving that generated events were accepted by the stream.

Decoded sample record:

```json
{
  "event_id": "evt-001209",
  "order_id": "ord-001209",
  "customer_id": "cus-0004",
  "store_id": "store-gangnam",
  "event_type": "PAID",
  "event_time": "2026-06-20T00:00:03Z",
  "items": [
    {
      "product_id": "bagel",
      "quantity": 1,
      "unit_price": 3800
    },
    {
      "product_id": "americano",
      "quantity": 2,
      "unit_price": 4500
    }
  ]
}
```

## Cleanup

The personal account deployment creates billable AWS resources. Destroy them
after screenshots and evidence collection:

```bash
terraform -chdir=infra/terraform/envs/dev destroy
```
