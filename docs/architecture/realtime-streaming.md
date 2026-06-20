# Real-Time Streaming Path

PeakOrder Insight has two real-time modes:

1. Local replay mode for portfolio demos.
2. AWS streaming mode for deployment.

## Local Replay Mode

```text
data/sample/order_events.jsonl
  -> src/streaming/live_dashboard_server.py
  -> /api/live-dashboard
  -> frontend polling every 2 seconds
```

Run it with:

```bash
make live-dashboard
```

Then open:

```text
http://127.0.0.1:8010/frontend/
```

This simulates real-time ingestion by applying order events in timed batches.

## AWS Streaming Mode

```text
Order event producer
  -> Amazon Kinesis Data Streams
  -> EMR/Flink/Spark streaming job
  -> Apache Paimon tables on S3
  -> S3 serving exports or API layer
  -> frontend dashboard
```

Terraform creates the Kinesis stream:

- `order_events_stream_name`
- `order_events_stream_arn`

Publish sample events to Kinesis:

```bash
python3 src/streaming/publish_order_events.py \
  --stream-name YOUR_STREAM_NAME \
  --region ap-northeast-2 \
  --batch-size 500 \
  --sleep-ms 100
```

## AWS Credentials

Do not paste AWS access keys into chat or source files. Use a local AWS profile:

```bash
aws configure sso --profile peakorder
export AWS_PROFILE=peakorder
```

Then run Terraform:

```bash
terraform -chdir=infra/terraform/envs/dev init
terraform -chdir=infra/terraform/envs/dev plan
```

The project does not need a chat session ID. It needs valid AWS credentials in
your local shell when you deploy.
