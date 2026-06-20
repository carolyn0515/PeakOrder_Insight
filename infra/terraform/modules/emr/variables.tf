variable "name_prefix" {
  description = "Prefix used for resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for EMR Serverless network placement."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet IDs for EMR Serverless jobs."
  type        = list(string)
}

variable "release_label" {
  description = "EMR release label."
  type        = string
  default     = "emr-7.2.0"
}

variable "maximum_cpu" {
  description = "Maximum CPU capacity for the EMR Serverless application."
  type        = string
  default     = "8 vCPU"
}

variable "maximum_memory" {
  description = "Maximum memory capacity for the EMR Serverless application."
  type        = string
  default     = "24 GB"
}

variable "maximum_disk" {
  description = "Maximum disk capacity for the EMR Serverless application."
  type        = string
  default     = "100 GB"
}

variable "idle_timeout_minutes" {
  description = "Minutes before an idle EMR Serverless application auto-stops."
  type        = number
  default     = 15
}
