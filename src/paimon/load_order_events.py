"""Load raw order events into Apache Paimon latest-state tables."""

from __future__ import annotations

import argparse

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T
from pyspark.sql.window import Window


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
    parser = argparse.ArgumentParser(description="Load order events into Paimon tables.")
    parser.add_argument("--warehouse", required=True, help="Paimon warehouse S3 URI.")
    parser.add_argument("--database", default="peakorder_insight", help="Catalog database name.")
    parser.add_argument("--catalog", default="paimon", help="Spark catalog name.")
    parser.add_argument("--input", required=True, help="Raw order event input path.")
    return parser.parse_args()


def create_spark(catalog: str, warehouse: str) -> SparkSession:
    return (
        SparkSession.builder.appName("peakorder-load-order-events")
        .config("spark.sql.extensions", "org.apache.paimon.spark.extensions.PaimonSparkSessionExtensions")
        .config(f"spark.sql.catalog.{catalog}", "org.apache.paimon.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{catalog}.warehouse", warehouse)
        .getOrCreate()
    )


def read_events(spark: SparkSession, input_path: str) -> DataFrame:
    return (
        spark.read.schema(ORDER_EVENT_SCHEMA)
        .json(input_path)
        .withColumn("event_ts", F.to_timestamp("event_time"))
        .withColumn("updated_at", F.current_timestamp())
        .filter(F.col("event_id").isNotNull())
        .filter(F.col("order_id").isNotNull())
        .filter(F.col("event_ts").isNotNull())
    )


def build_orders(events: DataFrame) -> DataFrame:
    item_total = F.expr(
        """
        aggregate(
          items,
          cast(0.0 as double),
          (acc, item) -> acc + (item.quantity * item.unit_price)
        )
        """
    )
    latest_order = Window.partitionBy("order_id").orderBy(F.col("event_time").desc(), F.col("event_id").desc())

    return (
        events.select(
            "event_id",
            "order_id",
            "customer_id",
            "store_id",
            F.col("event_type").alias("order_status"),
            item_total.cast("decimal(12,2)").alias("order_total"),
            F.col("event_ts").alias("event_time"),
            "updated_at",
        )
        .withColumn("_rank", F.row_number().over(latest_order))
        .filter(F.col("_rank") == 1)
        .drop("_rank", "event_id")
    )


def build_items(events: DataFrame) -> DataFrame:
    latest_item = Window.partitionBy("order_id", "product_id").orderBy(
        F.col("event_time").desc(),
        F.col("event_id").desc(),
    )

    return (
        events.withColumn("item", F.explode_outer("items"))
        .filter(F.col("item.product_id").isNotNull())
        .select(
            "event_id",
            "order_id",
            "store_id",
            F.col("item.product_id").alias("product_id"),
            F.col("item.quantity").cast("int").alias("quantity"),
            F.col("item.unit_price").cast("decimal(12,2)").alias("unit_price"),
            (F.col("item.quantity") * F.col("item.unit_price")).cast("decimal(12,2)").alias("line_total"),
            F.col("event_ts").alias("event_time"),
            "updated_at",
        )
        .withColumn("_rank", F.row_number().over(latest_item))
        .filter(F.col("_rank") == 1)
        .drop("_rank", "event_id")
    )


def build_daily_demand(items: DataFrame) -> DataFrame:
    return (
        items.groupBy(
            F.to_date("event_time").alias("demand_date"),
            "store_id",
            "product_id",
        )
        .agg(
            F.countDistinct("order_id").alias("order_count"),
            F.sum("quantity").cast("bigint").alias("units_sold"),
            F.sum("line_total").cast("decimal(18,2)").alias("gross_sales"),
        )
        .withColumn("updated_at", F.current_timestamp())
    )


def write_tables(spark: SparkSession, catalog: str, database: str, events: DataFrame) -> None:
    namespace = f"{catalog}.{database}"

    orders = build_orders(events)
    items = build_items(events)
    daily_demand = build_daily_demand(items)

    orders.createOrReplaceTempView("orders_batch")
    items.createOrReplaceTempView("order_items_batch")
    daily_demand.createOrReplaceTempView("product_demand_daily_batch")

    spark.sql(
        f"""
        INSERT INTO {namespace}.orders_latest
        SELECT * FROM orders_batch
        """
    )

    spark.sql(
        f"""
        INSERT INTO {namespace}.order_items_latest
        SELECT * FROM order_items_batch
        """
    )

    spark.sql(
        f"""
        INSERT INTO {namespace}.product_demand_daily
        SELECT * FROM product_demand_daily_batch
        """
    )


def main() -> None:
    args = parse_args()
    spark = create_spark(args.catalog, args.warehouse)

    try:
        events = read_events(spark, args.input)
        write_tables(spark, args.catalog, args.database, events)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
