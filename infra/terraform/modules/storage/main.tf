resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  raw_bucket_name       = coalesce(var.raw_bucket_name, "${var.name_prefix}-raw-${random_id.suffix.hex}")
  lakehouse_bucket_name = coalesce(var.lakehouse_bucket_name, "${var.name_prefix}-lakehouse-${random_id.suffix.hex}")
}

resource "aws_s3_bucket" "raw" {
  bucket = local.raw_bucket_name
}

resource "aws_s3_bucket" "lakehouse" {
  bucket = local.lakehouse_bucket_name
}

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "lakehouse" {
  bucket = aws_s3_bucket.lakehouse.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lakehouse" {
  bucket = aws_s3_bucket.lakehouse.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket = aws_s3_bucket.raw.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "lakehouse" {
  bucket = aws_s3_bucket.lakehouse.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "raw_prefixes" {
  for_each = toset(["orders/", "inventory/", "products/"])

  bucket  = aws_s3_bucket.raw.id
  key     = each.value
  content = ""
}

resource "aws_s3_object" "lakehouse_prefixes" {
  for_each = toset(["paimon/", "checkpoints/", "exports/"])

  bucket  = aws_s3_bucket.lakehouse.id
  key     = each.value
  content = ""
}
