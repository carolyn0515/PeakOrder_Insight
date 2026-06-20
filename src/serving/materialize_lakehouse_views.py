"""Materialize dashboard-ready lakehouse views without external Spark packages.

This job is intentionally dependency-light so it can run in private EMR
Serverless subnets. Paimon remains the target latest-state table format, but
this job creates portfolio evidence while Paimon runtime packaging is being
resolved.
"""

from __future__ import annotations

import argparse

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T


ORDER_EVENT_SCHEMA = T.StructType(
    [
        T.StructField("event_id", T.StringType(), nullable=False),
        T.StructField("order_id", T.StringType(), nullable=False),
        T.StructField("customer_id", T.StringType(), nullable=True),
        T.StructField("store_id", T.StringType(), nullable=True),
        T.StructField("event_type", T.StringType(), nullable=False),
        T.StructField("event_time", T.StringType(), nullable=False),
        T.StructField(
            "items",
            T.ArrayType(
                T.StructType(
                    [
                        T.StructField("product_id", T.StringType(), nullable=False),
                        T.StructField("quantity", T.IntegerType(), nullable=False),
                        T.StructField("unit_price", T.DoubleType(), nullable=False),
                    ]
                )
            ),
            nullable=True,
        ),
    ]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize PeakOrder lakehouse views.")
    parser.add_argument("--input", required=True, help="Raw order event JSONL input path.")
    parser.add_argument("--output", required=True, help="S3 prefix for materialized views.")
    parser.add_argument("--peak-threshold", type=float, default=2.0, help="Pressure ratio threshold.")
    parser.add_argument("--min-orders", type=int, default=100, help="Minimum hourly store orders for alerting.")
    return parser.parse_args()


def create_spark() -> SparkSession:
    return SparkSession.builder.appName("peakorder-materialize-lakehouse-views").getOrCreate()


def read_events(spark: SparkSession, input_path: str) -> DataFrame:
    return (
        spark.read.schema(ORDER_EVENT_SCHEMA)
        .json(input_path)
        .withColumn("event_ts", F.to_timestamp("event_time"))
        .filter(F.col("event_id").isNotNull())
        .filter(F.col("order_id").isNotNull())
        .filter(F.col("event_ts").isNotNull())
    )


def build_order_items(events: DataFrame) -> DataFrame:
    return (
        events.withColumn("item", F.explode("items"))
        .select(
            "event_id",
            "order_id",
            "customer_id",
            "store_id",
            "event_type",
            F.col("event_ts").alias("event_time"),
            F.col("item.product_id").alias("product_id"),
            F.col("item.quantity").cast("int").alias("quantity"),
            F.col("item.unit_price").cast("double").alias("unit_price"),
        )
        .withColumn("line_total", F.col("quantity") * F.col("unit_price"))
        .filter(F.col("product_id").isNotNull())
        .filter(F.col("quantity") > 0)
        .filter(F.col("unit_price") >= 0)
    )


def build_product_demand_daily(items: DataFrame) -> DataFrame:
    return (
        items.groupBy(F.to_date("event_time").alias("demand_date"), "store_id", "product_id")
        .agg(
            F.countDistinct("order_id").alias("order_count"),
            F.sum("quantity").cast("bigint").alias("units_sold"),
            F.sum("line_total").cast("decimal(18,2)").alias("gross_sales"),
        )
        .withColumn("updated_at", F.current_timestamp())
    )


def build_hourly_pressure(items: DataFrame) -> DataFrame:
    hourly = (
        items.groupBy(F.date_trunc("hour", "event_time").alias("hour_start"), "store_id")
        .agg(
            F.countDistinct("order_id").alias("order_count"),
            F.sum("quantity").cast("bigint").alias("units_sold"),
            F.sum("line_total").cast("decimal(18,2)").alias("gross_sales"),
        )
    )

    baseline = hourly.groupBy("store_id").agg(F.avg("order_count").alias("baseline_order_count"))

    return (
        hourly.join(baseline, on="store_id", how="left")
        .withColumn(
            "pressure_ratio",
            F.when(F.col("baseline_order_count") > 0, F.col("order_count") / F.col("baseline_order_count")).otherwise(F.lit(0.0)),
        )
        .withColumn("updated_at", F.current_timestamp())
    )


def build_alerts(pressure: DataFrame, peak_threshold: float, min_orders: int) -> DataFrame:
    return (
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


def write_view(df: DataFrame, output: str, name: str) -> None:
    df.coalesce(1).write.mode("overwrite").json(f"{output}/json/{name}")
    df.write.mode("overwrite").parquet(f"{output}/parquet/{name}")


def materialize(events: DataFrame, output: str, peak_threshold: float, min_orders: int) -> None:
    items = build_order_items(events).cache()
    daily_demand = build_product_demand_daily(items).cache()
    pressure = build_hourly_pressure(items).cache()
    alerts = build_alerts(pressure, peak_threshold, min_orders).cache()

    product_leaderboard = (
        daily_demand.groupBy("demand_date", "product_id")
        .agg(
            F.sum("order_count").alias("order_count"),
            F.sum("units_sold").alias("units_sold"),
            F.sum("gross_sales").cast("decimal(18,2)").alias("gross_sales"),
        )
        .withColumn("exported_at", F.current_timestamp())
    )

    write_view(items, output, "order_item_events")
    write_view(daily_demand, output, "product_demand_daily")
    write_view(pressure, output, "store_order_pressure_hourly")
    write_view(alerts, output, "peak_order_alerts")
    write_view(product_leaderboard, output, "product_leaderboard")

    print(f"materialized_order_item_rows={items.count()}")
    print(f"materialized_product_demand_rows={daily_demand.count()}")
    print(f"materialized_pressure_rows={pressure.count()}")
    print(f"materialized_alert_rows={alerts.count()}")
    print(f"materialized_output={output}")


def main() -> None:
    args = parse_args()
    spark = create_spark()

    try:
        events = read_events(spark, args.input).cache()
        print(f"materialized_raw_event_rows={events.count()}")
        materialize(events, args.output.rstrip("/"), args.peak_threshold, args.min_orders)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
