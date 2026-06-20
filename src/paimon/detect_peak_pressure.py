"""Detect hourly order pressure spikes and write Paimon alert tables."""

from __future__ import annotations

import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect peak order pressure from Paimon order items.")
    parser.add_argument("--warehouse", required=True, help="Paimon warehouse S3 URI.")
    parser.add_argument("--database", default="peakorder_insight", help="Catalog database name.")
    parser.add_argument("--catalog", default="paimon", help="Spark catalog name.")
    parser.add_argument("--peak-threshold", type=float, default=2.5, help="Pressure ratio threshold for alerts.")
    parser.add_argument("--min-orders", type=int, default=20, help="Minimum hourly orders before alerting.")
    return parser.parse_args()


def create_spark(catalog: str, warehouse: str) -> SparkSession:
    return (
        SparkSession.builder.appName("peakorder-detect-peak-pressure")
        .config(f"spark.sql.catalog.{catalog}", "org.apache.paimon.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{catalog}.warehouse", warehouse)
        .getOrCreate()
    )


def detect_peaks(spark: SparkSession, catalog: str, database: str, peak_threshold: float, min_orders: int) -> None:
    namespace = f"{catalog}.{database}"
    items = spark.table(f"{namespace}.order_items_latest")

    hourly = (
        items.groupBy(
            F.window("event_time", "1 hour").alias("hour_window"),
            "store_id",
        )
        .agg(
            F.countDistinct("order_id").alias("order_count"),
            F.sum("quantity").cast("bigint").alias("units_sold"),
            F.sum("line_total").cast("decimal(18,2)").alias("gross_sales"),
        )
        .select(
            F.col("hour_window.start").alias("hour_start"),
            "store_id",
            "order_count",
            "units_sold",
            "gross_sales",
        )
    )

    baseline_window = Window.partitionBy("store_id")
    pressure = (
        hourly.withColumn("baseline_order_count", F.avg("order_count").over(baseline_window))
        .withColumn(
            "pressure_ratio",
            F.when(F.col("baseline_order_count") > 0, F.col("order_count") / F.col("baseline_order_count")).otherwise(F.lit(0.0)),
        )
        .withColumn("updated_at", F.current_timestamp())
    )

    alerts = (
        pressure.filter((F.col("order_count") >= min_orders) & (F.col("pressure_ratio") >= peak_threshold))
        .withColumn("alert_id", F.concat_ws("#", F.col("store_id"), F.date_format("hour_start", "yyyyMMddHH")))
        .withColumn("severity", F.when(F.col("pressure_ratio") >= peak_threshold * 1.5, F.lit("CRITICAL")).otherwise(F.lit("WARNING")))
        .withColumn(
            "reason",
            F.concat(
                F.lit("Hourly order pressure ratio "),
                F.round("pressure_ratio", 2).cast("string"),
                F.lit(" exceeded threshold "),
                F.lit(str(peak_threshold)),
            ),
        )
        .withColumn("detected_at", F.current_timestamp())
        .select(
            "alert_id",
            "store_id",
            "hour_start",
            "order_count",
            "baseline_order_count",
            "pressure_ratio",
            "severity",
            "reason",
            "detected_at",
        )
    )

    pressure.createOrReplaceTempView("store_order_pressure_hourly_batch")
    alerts.createOrReplaceTempView("peak_order_alerts_batch")

    spark.sql(
        f"""
        MERGE INTO {namespace}.store_order_pressure_hourly target
        USING store_order_pressure_hourly_batch source
        ON target.hour_start = source.hour_start AND target.store_id = source.store_id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """
    )

    spark.sql(
        f"""
        MERGE INTO {namespace}.peak_order_alerts target
        USING peak_order_alerts_batch source
        ON target.alert_id = source.alert_id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """
    )


def main() -> None:
    args = parse_args()
    spark = create_spark(args.catalog, args.warehouse)

    try:
        detect_peaks(spark, args.catalog, args.database, args.peak_threshold, args.min_orders)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
