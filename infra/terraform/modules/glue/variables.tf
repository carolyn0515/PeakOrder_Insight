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

variable "pipeline_role_arn" {
  description = "Pipeline role ARN reserved for Glue jobs."
  type        = string
}
