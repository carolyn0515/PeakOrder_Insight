"""Export query-optimized dashboard views from Paimon tables."""

from __future__ import annotations

import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export dashboard-ready views from Paimon.")
    parser.add_argument("--warehouse", required=True, help="Paimon warehouse S3 URI.")
    parser.add_argument("--database", default="peakorder_insight", help="Catalog database name.")
    parser.add_argument("--catalog", default="paimon", help="Spark catalog name.")
    parser.add_argument("--output", required=True, help="S3 output prefix for exported views.")
    return parser.parse_args()


def create_spark(catalog: str, warehouse: str) -> SparkSession:
    return (
        SparkSession.builder.appName("peakorder-export-dashboard-views")
        .config(f"spark.sql.catalog.{catalog}", "org.apache.paimon.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{catalog}.warehouse", warehouse)
        .getOrCreate()
    )


def export_views(spark: SparkSession, catalog: str, database: str, output: str) -> None:
    namespace = f"{catalog}.{database}"

    daily_demand = spark.table(f"{namespace}.product_demand_daily")
    orders = spark.table(f"{namespace}.orders_latest")
    pressure = spark.table(f"{namespace}.store_order_pressure_hourly")
    alerts = spark.table(f"{namespace}.peak_order_alerts")

    product_leaderboard = (
        daily_demand.groupBy("demand_date", "product_id")
        .agg(
            F.sum("order_count").alias("order_count"),
            F.sum("units_sold").alias("units_sold"),
            F.sum("gross_sales").cast("decimal(18,2)").alias("gross_sales"),
        )
        .withColumn("exported_at", F.current_timestamp())
        .orderBy(F.col("demand_date").desc(), F.col("gross_sales").desc())
    )

    store_daily_summary = (
        daily_demand.groupBy("demand_date", "store_id")
        .agg(
            F.sum("order_count").alias("order_count"),
            F.sum("units_sold").alias("units_sold"),
            F.sum("gross_sales").cast("decimal(18,2)").alias("gross_sales"),
        )
        .withColumn("exported_at", F.current_timestamp())
        .orderBy(F.col("demand_date").desc(), F.col("store_id"))
    )

    order_status_summary = (
        orders.groupBy("order_status")
        .agg(
            F.count("*").alias("order_count"),
            F.sum("order_total").cast("decimal(18,2)").alias("gross_sales"),
            F.max("updated_at").alias("latest_update_at"),
        )
        .withColumn("exported_at", F.current_timestamp())
        .orderBy(F.col("order_count").desc())
    )

    peak_pressure = pressure.orderBy(F.col("hour_start").desc(), F.col("pressure_ratio").desc())
    peak_alerts = alerts.orderBy(F.col("hour_start").desc(), F.col("pressure_ratio").desc())

    product_leaderboard.coalesce(1).write.mode("overwrite").json(f"{output}/product_leaderboard")
    store_daily_summary.coalesce(1).write.mode("overwrite").json(f"{output}/store_daily_summary")
    order_status_summary.coalesce(1).write.mode("overwrite").json(f"{output}/order_status_summary")
    peak_pressure.coalesce(1).write.mode("overwrite").json(f"{output}/peak_pressure")
    peak_alerts.coalesce(1).write.mode("overwrite").json(f"{output}/peak_alerts")

    product_leaderboard.write.mode("overwrite").parquet(f"{output}/parquet/product_leaderboard")
    store_daily_summary.write.mode("overwrite").parquet(f"{output}/parquet/store_daily_summary")
    order_status_summary.write.mode("overwrite").parquet(f"{output}/parquet/order_status_summary")
    peak_pressure.write.mode("overwrite").parquet(f"{output}/parquet/peak_pressure")
    peak_alerts.write.mode("overwrite").parquet(f"{output}/parquet/peak_alerts")


def main() -> None:
    args = parse_args()
    spark = create_spark(args.catalog, args.warehouse)

    try:
        export_views(spark, args.catalog, args.database, args.output.rstrip("/"))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
