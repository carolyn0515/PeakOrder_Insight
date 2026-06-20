#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  submit_emr_serverless_job.sh \
    --application-id APP_ID \
    --execution-role-arn ROLE_ARN \
    --job-name JOB_NAME \
    --entry-point S3_SCRIPT_URI \
    --warehouse S3_PAIMON_WAREHOUSE \
    --database GLUE_DATABASE \
    [--input S3_INPUT_PATH]

The Paimon runtime package is supplied with spark.jars.packages. Override
PAIMON_SPARK_PACKAGE when you need a different Spark/Scala/Paimon build.
USAGE
}

APPLICATION_ID=""
EXECUTION_ROLE_ARN=""
JOB_NAME=""
ENTRY_POINT=""
WAREHOUSE=""
DATABASE=""
INPUT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --application-id) APPLICATION_ID="$2"; shift 2 ;;
    --execution-role-arn) EXECUTION_ROLE_ARN="$2"; shift 2 ;;
    --job-name) JOB_NAME="$2"; shift 2 ;;
    --entry-point) ENTRY_POINT="$2"; shift 2 ;;
    --warehouse) WAREHOUSE="$2"; shift 2 ;;
    --database) DATABASE="$2"; shift 2 ;;
    --input) INPUT_PATH="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$APPLICATION_ID" || -z "$EXECUTION_ROLE_ARN" || -z "$JOB_NAME" || -z "$ENTRY_POINT" || -z "$WAREHOUSE" || -z "$DATABASE" ]]; then
  usage
  exit 1
fi

PAIMON_SPARK_PACKAGE="${PAIMON_SPARK_PACKAGE:-org.apache.paimon:paimon-spark-3.5:1.0.1}"

ARGS=(--warehouse "$WAREHOUSE" --database "$DATABASE")
if [[ -n "$INPUT_PATH" ]]; then
  ARGS+=(--input "$INPUT_PATH")
fi

aws emr-serverless start-job-run \
  --application-id "$APPLICATION_ID" \
  --execution-role-arn "$EXECUTION_ROLE_ARN" \
  --name "$JOB_NAME" \
  --job-driver "$(jq -n \
    --arg entryPoint "$ENTRY_POINT" \
    --arg packages "$PAIMON_SPARK_PACKAGE" \
    --argjson args "$(printf '%s\n' "${ARGS[@]}" | jq -R . | jq -s .)" \
    '{sparkSubmit: {entryPoint: $entryPoint, entryPointArguments: $args, sparkSubmitParameters: ("--conf spark.jars.packages=" + $packages)}}')" \
  --configuration-overrides '{"monitoringConfiguration":{"cloudWatchLoggingConfiguration":{"enabled":true}}}'
