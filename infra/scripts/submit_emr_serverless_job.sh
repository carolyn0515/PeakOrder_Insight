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
    [--region AWS_REGION] \
    [--input S3_INPUT_PATH]

By default the Paimon runtime package is resolved with spark.jars.packages.
For private subnets without Maven access, set PAIMON_SPARK_JAR_URI to an S3 jar
URI and the job will use --jars instead.
USAGE
}

APPLICATION_ID=""
EXECUTION_ROLE_ARN=""
JOB_NAME=""
ENTRY_POINT=""
WAREHOUSE=""
DATABASE=""
INPUT_PATH=""
REGION="${AWS_REGION:-ap-northeast-2}"
SPARK_CATALOG="${SPARK_CATALOG:-paimon}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --application-id) APPLICATION_ID="$2"; shift 2 ;;
    --execution-role-arn) EXECUTION_ROLE_ARN="$2"; shift 2 ;;
    --job-name) JOB_NAME="$2"; shift 2 ;;
    --entry-point) ENTRY_POINT="$2"; shift 2 ;;
    --warehouse) WAREHOUSE="$2"; shift 2 ;;
    --database) DATABASE="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
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
PAIMON_SPARK_JAR_URI="${PAIMON_SPARK_JAR_URI:-}"
SPARK_RESOURCE_PARAMETERS="${SPARK_RESOURCE_PARAMETERS:---conf spark.dynamicAllocation.enabled=false --conf spark.executor.instances=1 --conf spark.executor.cores=1 --conf spark.executor.memory=2g --conf spark.driver.cores=1 --conf spark.driver.memory=2g}"
PAIMON_SPARK_PARAMETERS="--conf spark.sql.extensions=org.apache.paimon.spark.extensions.PaimonSparkSessionExtensions --conf spark.sql.catalog.${SPARK_CATALOG}=org.apache.paimon.spark.SparkCatalog --conf spark.sql.catalog.${SPARK_CATALOG}.warehouse=${WAREHOUSE}"

ARGS=(--warehouse "$WAREHOUSE" --database "$DATABASE")
if [[ -n "$INPUT_PATH" ]]; then
  ARGS+=(--input "$INPUT_PATH")
fi

aws emr-serverless start-job-run \
  --region "$REGION" \
  --application-id "$APPLICATION_ID" \
  --execution-role-arn "$EXECUTION_ROLE_ARN" \
  --name "$JOB_NAME" \
  --job-driver "$(jq -n \
    --arg entryPoint "$ENTRY_POINT" \
    --arg packages "$PAIMON_SPARK_PACKAGE" \
    --arg jarUri "$PAIMON_SPARK_JAR_URI" \
    --arg paimonParams "$PAIMON_SPARK_PARAMETERS" \
    --arg resourceParams "$SPARK_RESOURCE_PARAMETERS" \
    --argjson args "$(printf '%s\n' "${ARGS[@]}" | jq -R . | jq -s .)" \
    '{
      sparkSubmit: {
        entryPoint: $entryPoint,
        entryPointArguments: $args,
        sparkSubmitParameters: (
          if $jarUri == "" then
            "--conf spark.jars.packages=" + $packages + " " + $paimonParams + " " + $resourceParams
          else
            "--jars " + $jarUri + " " + $paimonParams + " " + $resourceParams
          end
        )
      }
    }')" \
  --configuration-overrides '{"monitoringConfiguration":{"cloudWatchLoggingConfiguration":{"enabled":true}}}'
