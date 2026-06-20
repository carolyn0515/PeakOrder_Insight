#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  upload_job_assets.sh \
    --lakehouse-bucket LAKEHOUSE_BUCKET \
    --raw-bucket RAW_BUCKET

Uploads Spark job scripts to the lakehouse bucket and sample order events to
the raw bucket.
USAGE
}

LAKEHOUSE_BUCKET=""
RAW_BUCKET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lakehouse-bucket) LAKEHOUSE_BUCKET="$2"; shift 2 ;;
    --raw-bucket) RAW_BUCKET="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$LAKEHOUSE_BUCKET" || -z "$RAW_BUCKET" ]]; then
  usage
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

aws s3 cp "$REPO_ROOT/src/paimon/bootstrap_tables.py" "s3://$LAKEHOUSE_BUCKET/jobs/bootstrap_tables.py"
aws s3 cp "$REPO_ROOT/src/paimon/load_order_events.py" "s3://$LAKEHOUSE_BUCKET/jobs/load_order_events.py"
aws s3 cp "$REPO_ROOT/data/sample/order_events.jsonl" "s3://$RAW_BUCKET/orders/order_events.jsonl"

echo "Uploaded Paimon job assets and sample order events."
