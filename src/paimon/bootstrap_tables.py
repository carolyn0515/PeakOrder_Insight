"""Create Apache Paimon catalog objects for PeakOrder Insight.

This job is intended to run on EMR Serverless with Spark and the Paimon Spark
runtime package supplied through spark-submit configuration.
"""

from __future__ import annotations

import argparse

from pyspark.sql import SparkSession


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap Paimon lakehouse tables.")
    parser.add_argument("--warehouse", required=True, help="Paimon warehouse S3 URI.")
    parser.add_argument("--database", default="peakorder_insight", help="Catalog database name.")
    parser.add_argument("--catalog", default="paimon", help="Spark catalog name.")
    return parser.parse_args()


def create_spark(catalog: str, warehouse: str) -> SparkSession:
    return (
        SparkSession.builder.appName("peakorder-paimon-bootstrap")
        .config(f"spark.sql.catalog.{catalog}", "org.apache.paimon.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{catalog}.warehouse", warehouse)
        .getOrCreate()
    )


def bootstrap_tables(spark: SparkSession, catalog: str, database: str) -> None:
    namespace = f"{catalog}.{database}"

    spark.sql(f"CREATE DATABASE IF NOT EXISTS {namespace}")

    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {namespace}.orders_latest (
          order_id STRING,
          customer_id STRING,
          store_id STRING,
          order_status STRING,
          order_total DECIMAL(12, 2),
          event_time TIMESTAMP,
          updated_at TIMESTAMP,
          PRIMARY KEY (order_id) NOT ENFORCED
        ) WITH (
          'bucket' = '4',
          'changelog-producer' = 'input'
        )
        """
    )

    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {namespace}.order_items_latest (
          order_id STRING,
          store_id STRING,
          product_id STRING,
          quantity INT,
          unit_price DECIMAL(12, 2),
          line_total DECIMAL(12, 2),
          event_time TIMESTAMP,
          updated_at TIMESTAMP,
          PRIMARY KEY (order_id, product_id) NOT ENFORCED
        ) WITH (
          'bucket' = '4',
          'changelog-producer' = 'input'
        )
        """
    )

    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {namespace}.product_demand_daily (
          demand_date DATE,
          store_id STRING,
          product_id STRING,
          order_count BIGINT,
          units_sold BIGINT,
          gross_sales DECIMAL(18, 2),
          updated_at TIMESTAMP,
          PRIMARY KEY (demand_date, store_id, product_id) NOT ENFORCED
        ) WITH (
          'bucket' = '4',
          'changelog-producer' = 'input'
        )
        """
    )

    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {namespace}.order_anomaly_events (
          event_id STRING,
          order_id STRING,
          anomaly_type STRING,
          severity STRING,
          reason STRING,
          event_time TIMESTAMP,
          detected_at TIMESTAMP,
          PRIMARY KEY (event_id) NOT ENFORCED
        ) WITH (
          'bucket' = '2',
          'changelog-producer' = 'input'
        )
        """
    )

    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {namespace}.store_order_pressure_hourly (
          hour_start TIMESTAMP,
          store_id STRING,
          order_count BIGINT,
          units_sold BIGINT,
          gross_sales DECIMAL(18, 2),
          baseline_order_count DOUBLE,
          pressure_ratio DOUBLE,
          updated_at TIMESTAMP,
          PRIMARY KEY (hour_start, store_id) NOT ENFORCED
        ) WITH (
          'bucket' = '4',
          'changelog-producer' = 'input'
        )
        """
    )

    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {namespace}.peak_order_alerts (
          alert_id STRING,
          store_id STRING,
          hour_start TIMESTAMP,
          order_count BIGINT,
          baseline_order_count DOUBLE,
          pressure_ratio DOUBLE,
          severity STRING,
          reason STRING,
          detected_at TIMESTAMP,
          PRIMARY KEY (alert_id) NOT ENFORCED
        ) WITH (
          'bucket' = '2',
          'changelog-producer' = 'input'
        )
        """
    )


def main() -> None:
    args = parse_args()
    spark = create_spark(args.catalog, args.warehouse)

    try:
        bootstrap_tables(spark, args.catalog, args.database)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
