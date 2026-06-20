variable "name_prefix" {
  description = "Prefix used for resource names."
  type        = string
}

variable "shard_count" {
  description = "Number of Kinesis shards for order events."
  type        = number
  default     = 2
}

variable "retention_hours" {
  description = "Kinesis stream retention period in hours."
  type        = number
  default     = 24
}
