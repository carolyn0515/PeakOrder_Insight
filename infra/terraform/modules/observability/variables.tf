variable "name_prefix" {
  description = "Prefix used for resource names."
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention period."
  type        = number
}

variable "order_stream_name" {
  description = "Kinesis stream name used by CloudWatch ingestion alarms."
  type        = string
}
