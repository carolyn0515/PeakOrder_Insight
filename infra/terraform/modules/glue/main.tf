resource "aws_glue_catalog_database" "lakehouse" {
  name        = var.database_name
  description = "PeakOrder Insight lakehouse catalog database."

  parameters = {
    paimon_warehouse = var.paimon_warehouse
  }
}

resource "aws_glue_catalog_table" "raw_order_events_json" {
  name          = "raw_order_events_json"
  database_name = aws_glue_catalog_database.lakehouse.name
  description   = "Raw PeakOrder order event JSONL files landed from Kinesis replay."
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    classification = "json"
    compressionType = "none"
    evidence        = "raw-stream-landing"
    project         = "peakorder-insight"
    typeOfData      = "file"
  }

  storage_descriptor {
    location      = "s3://${var.raw_bucket_name}/orders/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    columns {
      name = "event_id"
      type = "string"
    }

    columns {
      name = "order_id"
      type = "string"
    }

    columns {
      name = "customer_id"
      type = "string"
    }

    columns {
      name = "store_id"
      type = "string"
    }

    columns {
      name = "event_type"
      type = "string"
    }

    columns {
      name = "event_time"
      type = "string"
    }

    columns {
      name = "items"
      type = "array<struct<product_id:string,quantity:int,unit_price:double>>"
    }

    ser_de_info {
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"

      parameters = {
        paths = "customer_id,event_id,event_time,event_type,items,order_id,store_id"
      }
    }
  }
}

resource "aws_glue_catalog_table" "product_demand_daily" {
  name          = "product_demand_daily"
  database_name = aws_glue_catalog_database.lakehouse.name
  description   = "Materialized daily product demand exported by EMR Serverless."
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    classification = "parquet"
    project        = "peakorder-insight"
    typeOfData     = "file"
  }

  storage_descriptor {
    location      = "s3://${var.lakehouse_bucket_name}/exports/parquet/product_demand_daily/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    columns {
      name = "demand_date"
      type = "date"
    }

    columns {
      name = "store_id"
      type = "string"
    }

    columns {
      name = "product_id"
      type = "string"
    }

    columns {
      name = "order_count"
      type = "bigint"
    }

    columns {
      name = "units_sold"
      type = "bigint"
    }

    columns {
      name = "gross_sales"
      type = "decimal(18,2)"
    }

    columns {
      name = "updated_at"
      type = "timestamp"
    }

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }
  }
}

resource "aws_glue_catalog_table" "store_order_pressure_hourly" {
  name          = "store_order_pressure_hourly"
  database_name = aws_glue_catalog_database.lakehouse.name
  description   = "Hourly store pressure ratios produced by EMR Serverless."
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    classification = "parquet"
    project        = "peakorder-insight"
    typeOfData     = "file"
  }

  storage_descriptor {
    location      = "s3://${var.lakehouse_bucket_name}/exports/parquet/store_order_pressure_hourly/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    columns {
      name = "store_id"
      type = "string"
    }

    columns {
      name = "hour_start"
      type = "timestamp"
    }

    columns {
      name = "order_count"
      type = "bigint"
    }

    columns {
      name = "units_sold"
      type = "bigint"
    }

    columns {
      name = "gross_sales"
      type = "decimal(18,2)"
    }

    columns {
      name = "baseline_order_count"
      type = "double"
    }

    columns {
      name = "pressure_ratio"
      type = "double"
    }

    columns {
      name = "updated_at"
      type = "timestamp"
    }

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }
  }
}

resource "aws_glue_catalog_table" "peak_order_alerts" {
  name          = "peak_order_alerts"
  database_name = aws_glue_catalog_database.lakehouse.name
  description   = "Peak order pressure alerts produced from hourly pressure ratios."
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    classification = "parquet"
    project        = "peakorder-insight"
    typeOfData     = "file"
  }

  storage_descriptor {
    location      = "s3://${var.lakehouse_bucket_name}/exports/parquet/peak_order_alerts/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    columns {
      name = "alert_id"
      type = "string"
    }

    columns {
      name = "store_id"
      type = "string"
    }

    columns {
      name = "hour_start"
      type = "timestamp"
    }

    columns {
      name = "order_count"
      type = "bigint"
    }

    columns {
      name = "baseline_order_count"
      type = "double"
    }

    columns {
      name = "pressure_ratio"
      type = "double"
    }

    columns {
      name = "severity"
      type = "string"
    }

    columns {
      name = "reason"
      type = "string"
    }

    columns {
      name = "detected_at"
      type = "timestamp"
    }

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }
  }
}

resource "aws_glue_catalog_table" "product_leaderboard" {
  name          = "product_leaderboard"
  database_name = aws_glue_catalog_database.lakehouse.name
  description   = "Dashboard-ready product leaderboard exported by EMR Serverless."
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    classification = "parquet"
    project        = "peakorder-insight"
    typeOfData     = "file"
  }

  storage_descriptor {
    location      = "s3://${var.lakehouse_bucket_name}/exports/parquet/product_leaderboard/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    columns {
      name = "demand_date"
      type = "date"
    }

    columns {
      name = "product_id"
      type = "string"
    }

    columns {
      name = "order_count"
      type = "bigint"
    }

    columns {
      name = "units_sold"
      type = "bigint"
    }

    columns {
      name = "gross_sales"
      type = "decimal(18,2)"
    }

    columns {
      name = "exported_at"
      type = "timestamp"
    }

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }
  }
}

resource "aws_glue_security_configuration" "pipeline" {
  name = "${var.name_prefix}-glue-security"

  encryption_configuration {
    cloudwatch_encryption {
      cloudwatch_encryption_mode = "DISABLED"
    }

    job_bookmarks_encryption {
      job_bookmarks_encryption_mode = "DISABLED"
    }

    s3_encryption {
      s3_encryption_mode = "SSE-S3"
    }
  }
}
