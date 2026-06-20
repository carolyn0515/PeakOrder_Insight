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

variable "log_retention_days" {
  description = "CloudWatch log retention period."
  type        = number
  default     = 14
}
