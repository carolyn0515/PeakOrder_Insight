"""Airflow DAG for the PeakOrder Insight Paimon lakehouse pipeline."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
try:
    from airflow.sdk import dag, task
except ImportError:
    from airflow.decorators import dag, task


AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
PROJECT_NAME = os.getenv("PROJECT_NAME", "peakorder-insight")
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

REPO_ROOT = Path(os.getenv("PEAKORDER_REPO_ROOT", "/opt/airflow/PeakOrder_Insight"))
LAKEHOUSE_BUCKET = os.getenv("LAKEHOUSE_BUCKET", "")
RAW_BUCKET = os.getenv("RAW_BUCKET", "")
APPLICATION_ID = os.getenv("EMR_SERVERLESS_APPLICATION_ID", "")
EXECUTION_ROLE_ARN = os.getenv("PIPELINE_ROLE_ARN", "")
PAIMON_WAREHOUSE = os.getenv("PAIMON_WAREHOUSE", f"s3://{LAKEHOUSE_BUCKET}/paimon")
GLUE_DATABASE = os.getenv("GLUE_DATABASE_NAME", f"peakorder_insight_{ENVIRONMENT}")
PAIMON_SPARK_PACKAGE = os.getenv("PAIMON_SPARK_PACKAGE", "org.apache.paimon:paimon-spark-3.5:1.0.1")

JOB_PREFIX = f"{PROJECT_NAME}-{ENVIRONMENT}"
BOOTSTRAP_SCRIPT_KEY = "jobs/bootstrap_tables.py"
LOAD_EVENTS_SCRIPT_KEY = "jobs/load_order_events.py"
VALIDATE_EVENTS_SCRIPT_KEY = "jobs/validate_order_events.py"
SAMPLE_EVENTS_KEY = "orders/order_events.jsonl"


def s3_client():
    import boto3

    return boto3.client("s3", region_name=AWS_REGION)


def emr_client():
    import boto3

    return boto3.client("emr-serverless", region_name=AWS_REGION)


def require_settings(required: dict[str, str]) -> None:
    missing = [name for name, value in required.items() if not value]
    if missing:
        joined = ", ".join(sorted(missing))
        raise RuntimeError(f"Missing required Airflow environment variables: {joined}")


def upload_file(bucket: str, key: str, local_path: Path) -> str:
    require_settings({"bucket": bucket})
    s3_client().upload_file(str(local_path), bucket, key)
    return f"s3://{bucket}/{key}"


def submit_spark_job(job_name: str, entry_point: str, arguments: list[str]) -> str:
    require_settings({
        "EMR_SERVERLESS_APPLICATION_ID": APPLICATION_ID,
        "PIPELINE_ROLE_ARN": EXECUTION_ROLE_ARN,
        "PAIMON_WAREHOUSE": PAIMON_WAREHOUSE,
        "GLUE_DATABASE_NAME": GLUE_DATABASE,
    })
    response = emr_client().start_job_run(
        applicationId=APPLICATION_ID,
        executionRoleArn=EXECUTION_ROLE_ARN,
        name=job_name,
        jobDriver={
            "sparkSubmit": {
                "entryPoint": entry_point,
                "entryPointArguments": arguments,
                "sparkSubmitParameters": f"--conf spark.jars.packages={PAIMON_SPARK_PACKAGE}",
            }
        },
        configurationOverrides={
            "monitoringConfiguration": {
                "cloudWatchLoggingConfiguration": {
                    "enabled": True,
                    "logGroupName": f"/aws/peakorder/{JOB_PREFIX}/pipeline",
                }
            }
        },
    )
    return response["jobRunId"]


def wait_for_job(job_run_id: str, poll_seconds: int = 30) -> str:
    terminal_states = {"SUCCESS", "FAILED", "CANCELLING", "CANCELLED"}

    while True:
        response = emr_client().get_job_run(applicationId=APPLICATION_ID, jobRunId=job_run_id)
        state = response["jobRun"]["state"]

        if state in terminal_states:
            if state != "SUCCESS":
                reason = response["jobRun"].get("stateDetails", "No state details returned.")
                raise RuntimeError(f"EMR Serverless job {job_run_id} finished with {state}: {reason}")
            return state

        time.sleep(poll_seconds)


@dag(
    dag_id="peakorder_paimon_pipeline",
    description="Bootstrap and load PeakOrder Insight Paimon lakehouse tables.",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    default_args={
        "owner": "data-platform",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["peakorder", "paimon", "emr-serverless"],
)
def peakorder_paimon_pipeline():
    @task
    def upload_assets() -> dict[str, str]:
        bootstrap_uri = upload_file(
            LAKEHOUSE_BUCKET,
            BOOTSTRAP_SCRIPT_KEY,
            REPO_ROOT / "src/paimon/bootstrap_tables.py",
        )
        load_events_uri = upload_file(
            LAKEHOUSE_BUCKET,
            LOAD_EVENTS_SCRIPT_KEY,
            REPO_ROOT / "src/paimon/load_order_events.py",
        )
        validate_events_uri = upload_file(
            LAKEHOUSE_BUCKET,
            VALIDATE_EVENTS_SCRIPT_KEY,
            REPO_ROOT / "src/quality/validate_order_events.py",
        )
        raw_events_uri = upload_file(
            RAW_BUCKET,
            SAMPLE_EVENTS_KEY,
            REPO_ROOT / "data/sample/order_events.jsonl",
        )

        return {
            "bootstrap_uri": bootstrap_uri,
            "load_events_uri": load_events_uri,
            "validate_events_uri": validate_events_uri,
            "raw_events_uri": raw_events_uri,
        }

    @task
    def validate_order_events(assets: dict[str, str]) -> str:
        job_run_id = submit_spark_job(
            job_name=f"{JOB_PREFIX}-validate-order-events",
            entry_point=assets["validate_events_uri"],
            arguments=["--input", assets["raw_events_uri"], "--max-error-ratio", "0.0"],
        )
        return wait_for_job(job_run_id)

    @task
    def bootstrap_tables(assets: dict[str, str], _: str) -> str:
        job_run_id = submit_spark_job(
            job_name=f"{JOB_PREFIX}-bootstrap-paimon",
            entry_point=assets["bootstrap_uri"],
            arguments=["--warehouse", PAIMON_WAREHOUSE, "--database", GLUE_DATABASE],
        )
        return wait_for_job(job_run_id)

    @task
    def load_order_events(assets: dict[str, str], _: str) -> str:
        job_run_id = submit_spark_job(
            job_name=f"{JOB_PREFIX}-load-order-events",
            entry_point=assets["load_events_uri"],
            arguments=[
                "--warehouse",
                PAIMON_WAREHOUSE,
                "--database",
                GLUE_DATABASE,
                "--input",
                assets["raw_events_uri"],
            ],
        )
        return wait_for_job(job_run_id)

    uploaded_assets = upload_assets()
    validation_state = validate_order_events(uploaded_assets)
    bootstrap_state = bootstrap_tables(uploaded_assets, validation_state)
    load_order_events(uploaded_assets, bootstrap_state)


peakorder_paimon_pipeline()
