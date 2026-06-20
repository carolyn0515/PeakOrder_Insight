variable "project_name" {
  description = "Project name used for resource naming and tags."
  type        = string
  default     = "peakorder-insight"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for the environment."
  type        = string
  default     = "ap-northeast-2"
}

variable "availability_zones" {
  description = "Availability zones for private subnets."
  type        = list(string)
  default     = ["ap-northeast-2a", "ap-northeast-2c"]
}

variable "vpc_cidr" {
  description = "CIDR block for the project VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "raw_bucket_name" {
  description = "Optional explicit name for the raw S3 bucket. Leave null for generated name."
  type        = string
  default     = null
}

variable "lakehouse_bucket_name" {
  description = "Optional explicit name for the lakehouse S3 bucket. Leave null for generated name."
  type        = string
  default     = null
}

variable "glue_database_name" {
  description = "Glue Data Catalog database name for lakehouse tables."
  type        = string
  default     = "peakorder_insight_dev"
}

variable "emr_release_label" {
  description = "EMR release label for the Serverless Spark application."
  type        = string
  default     = "emr-7.2.0"
}

variable "emr_maximum_cpu" {
  description = "Maximum CPU capacity for the EMR Serverless application."
  type        = string
  default     = "8 vCPU"
}

variable "emr_maximum_memory" {
  description = "Maximum memory capacity for the EMR Serverless application."
  type        = string
  default     = "24 GB"
}

variable "emr_maximum_disk" {
  description = "Maximum disk capacity for the EMR Serverless application."
  type        = string
  default     = "100 GB"
}

variable "emr_idle_timeout_minutes" {
  description = "Minutes before an idle EMR Serverless application auto-stops."
  type        = number
  default     = 15
}

variable "kinesis_shard_count" {
  description = "Number of Kinesis shards for order event streaming."
  type        = number
  default     = 2
}

variable "kinesis_retention_hours" {
  description = "Kinesis stream retention period in hours."
  type        = number
  default     = 24
}

variable "log_retention_days" {
  description = "CloudWatch log retention period."
  type        = number
  default     = 14
}
