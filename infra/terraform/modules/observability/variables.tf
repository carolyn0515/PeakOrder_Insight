variable "name_prefix" {
  description = "Prefix used for resource names."
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention period."
  type        = number
}
