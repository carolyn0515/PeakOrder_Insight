resource "aws_glue_catalog_database" "lakehouse" {
  name        = var.database_name
  description = "PeakOrder Insight lakehouse catalog database."

  parameters = {
    paimon_warehouse = var.paimon_warehouse
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
