output "raw_bucket_name" {
  description = "Raw event bucket name."
  value       = module.storage.raw_bucket_name
}

output "lakehouse_bucket_name" {
  description = "Lakehouse bucket name."
  value       = module.storage.lakehouse_bucket_name
}

output "paimon_warehouse_uri" {
  description = "S3 URI for the Apache Paimon warehouse."
  value       = module.storage.paimon_warehouse_uri
}

output "glue_database_name" {
  description = "Glue database for lakehouse tables."
  value       = module.glue.database_name
}

output "pipeline_role_arn" {
  description = "IAM role ARN for pipeline jobs."
  value       = module.iam.pipeline_role_arn
}
