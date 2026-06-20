output "raw_bucket_name" {
  description = "Raw bucket name."
  value       = aws_s3_bucket.raw.bucket
}

output "raw_bucket_arn" {
  description = "Raw bucket ARN."
  value       = aws_s3_bucket.raw.arn
}

output "lakehouse_bucket_name" {
  description = "Lakehouse bucket name."
  value       = aws_s3_bucket.lakehouse.bucket
}

output "lakehouse_bucket_arn" {
  description = "Lakehouse bucket ARN."
  value       = aws_s3_bucket.lakehouse.arn
}

output "paimon_warehouse_uri" {
  description = "Paimon warehouse S3 URI."
  value       = "s3://${aws_s3_bucket.lakehouse.bucket}/paimon"
}
