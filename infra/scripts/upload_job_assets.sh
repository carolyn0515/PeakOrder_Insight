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
BASE_ORDERS_PER_HOUR="${BASE_ORDERS_PER_HOUR:-1000}"
PEAK_MULTIPLIER="${PEAK_MULTIPLIER:-8}"

python3 "$REPO_ROOT/src/ingestion/generate_peak_order_events.py" \
  --output "$REPO_ROOT/data/sample/order_events.jsonl" \
  --base-orders-per-hour "$BASE_ORDERS_PER_HOUR" \
  --peak-multiplier "$PEAK_MULTIPLIER"

aws s3 cp "$REPO_ROOT/src/paimon/bootstrap_tables.py" "s3://$LAKEHOUSE_BUCKET/jobs/bootstrap_tables.py"
aws s3 cp "$REPO_ROOT/src/paimon/load_order_events.py" "s3://$LAKEHOUSE_BUCKET/jobs/load_order_events.py"
aws s3 cp "$REPO_ROOT/src/quality/validate_order_events.py" "s3://$LAKEHOUSE_BUCKET/jobs/validate_order_events.py"
aws s3 cp "$REPO_ROOT/src/paimon/detect_peak_pressure.py" "s3://$LAKEHOUSE_BUCKET/jobs/detect_peak_pressure.py"
aws s3 cp "$REPO_ROOT/src/serving/export_dashboard_views.py" "s3://$LAKEHOUSE_BUCKET/jobs/export_dashboard_views.py"
aws s3 cp "$REPO_ROOT/src/serving/materialize_lakehouse_views.py" "s3://$LAKEHOUSE_BUCKET/jobs/materialize_lakehouse_views.py"
aws s3 cp "$REPO_ROOT/data/sample/order_events.jsonl" "s3://$RAW_BUCKET/orders/order_events.jsonl"

echo "Uploaded Paimon job assets and sample order events."
