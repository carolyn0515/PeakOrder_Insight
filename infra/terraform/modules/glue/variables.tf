variable "name_prefix" {
  description = "Prefix used for resource names."
  type        = string
}

variable "database_name" {
  description = "Glue database name."
  type        = string
}

variable "paimon_warehouse" {
  description = "S3 URI for the Paimon warehouse."
  type        = string
}

variable "raw_bucket_name" {
  description = "Raw S3 bucket name for external Glue tables."
  type        = string
}

variable "lakehouse_bucket_name" {
  description = "Lakehouse S3 bucket name for materialized export tables."
  type        = string
}

variable "pipeline_role_arn" {
  description = "Pipeline role ARN reserved for Glue jobs."
  type        = string
}
