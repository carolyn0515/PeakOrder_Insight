variable "name_prefix" {
  description = "Prefix used for resource names."
  type        = string
}

variable "raw_bucket_arn" {
  description = "Raw bucket ARN."
  type        = string
}

variable "lakehouse_bucket_arn" {
  description = "Lakehouse bucket ARN."
  type        = string
}

variable "order_stream_arn" {
  description = "Kinesis order events stream ARN."
  type        = string
}
