"""Validate raw order events before loading them into Paimon."""

from __future__ import annotations

import argparse

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T


ORDER_EVENT_SCHEMA = T.StructType(
    [
        T.StructField("event_id", T.StringType(), nullable=True),
        T.StructField("order_id", T.StringType(), nullable=True),
        T.StructField("customer_id", T.StringType(), nullable=True),
        T.StructField("store_id", T.StringType(), nullable=True),
        T.StructField("event_type", T.StringType(), nullable=True),
        T.StructField("event_time", T.StringType(), nullable=True),
        T.StructField(
            "items",
            T.ArrayType(
                T.StructType(
                    [
                        T.StructField("product_id", T.StringType(), nullable=True),
                        T.StructField("quantity", T.IntegerType(), nullable=True),
                        T.StructField("unit_price", T.DoubleType(), nullable=True),
                    ]
                )
            ),
            nullable=True,
        ),
    ]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate raw order event JSON records.")
    parser.add_argument("--input", required=True, help="Raw order event input path.")
    parser.add_argument("--max-error-ratio", type=float, default=0.0, help="Allowed invalid record ratio.")
    return parser.parse_args()


def create_spark() -> SparkSession:
    return SparkSession.builder.appName("peakorder-validate-order-events").getOrCreate()


def read_events(spark: SparkSession, input_path: str) -> DataFrame:
    return spark.read.schema(ORDER_EVENT_SCHEMA).json(input_path).withColumn("event_ts", F.to_timestamp("event_time"))


def add_quality_flags(events: DataFrame) -> DataFrame:
    has_items = F.col("items").isNotNull() & (F.size("items") > 0)
    invalid_items = F.exists(
        "items",
        lambda item: item.product_id.isNull() | item.quantity.isNull() | (item.quantity <= 0) | item.unit_price.isNull() | (item.unit_price < 0),
    )

    return (
        events.withColumn("missing_event_id", F.col("event_id").isNull())
        .withColumn("missing_order_id", F.col("order_id").isNull())
        .withColumn("missing_event_type", F.col("event_type").isNull())
        .withColumn("invalid_event_time", F.col("event_ts").isNull())
        .withColumn("missing_items", ~has_items)
        .withColumn("invalid_items", F.when(has_items, invalid_items).otherwise(F.lit(True)))
        .withColumn(
            "is_valid",
            ~(
                F.col("missing_event_id")
                | F.col("missing_order_id")
                | F.col("missing_event_type")
                | F.col("invalid_event_time")
                | F.col("missing_items")
                | F.col("invalid_items")
            ),
        )
    )


def validate(events: DataFrame, max_error_ratio: float) -> None:
    flagged = add_quality_flags(events).cache()

    total_count = flagged.count()
    invalid_count = flagged.filter(~F.col("is_valid")).count()
    error_ratio = 0.0 if total_count == 0 else invalid_count / total_count

    print(f"quality_total_records={total_count}")
    print(f"quality_invalid_records={invalid_count}")
    print(f"quality_error_ratio={error_ratio:.6f}")

    if total_count == 0:
        raise RuntimeError("No order event records found.")

    if error_ratio > max_error_ratio:
        invalid_summary = (
            flagged.filter(~F.col("is_valid"))
            .agg(
                F.sum(F.col("missing_event_id").cast("int")).alias("missing_event_id"),
                F.sum(F.col("missing_order_id").cast("int")).alias("missing_order_id"),
                F.sum(F.col("missing_event_type").cast("int")).alias("missing_event_type"),
                F.sum(F.col("invalid_event_time").cast("int")).alias("invalid_event_time"),
                F.sum(F.col("missing_items").cast("int")).alias("missing_items"),
                F.sum(F.col("invalid_items").cast("int")).alias("invalid_items"),
            )
            .collect()[0]
            .asDict()
        )
        raise RuntimeError(f"Order event quality check failed: {invalid_summary}")


def main() -> None:
    args = parse_args()
    spark = create_spark()

    try:
        events = read_events(spark, args.input)
        validate(events, args.max_error_ratio)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
