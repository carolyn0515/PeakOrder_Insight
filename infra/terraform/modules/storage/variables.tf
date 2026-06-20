variable "name_prefix" {
  description = "Prefix used for resource names."
  type        = string
}

variable "raw_bucket_name" {
  description = "Optional explicit raw bucket name."
  type        = string
  default     = null
}

variable "lakehouse_bucket_name" {
  description = "Optional explicit lakehouse bucket name."
  type        = string
  default     = null
}
