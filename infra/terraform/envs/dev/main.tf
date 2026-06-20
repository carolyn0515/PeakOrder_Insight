locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

module "network" {
  source = "../../modules/network"

  name_prefix        = local.name_prefix
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
}

module "storage" {
  source = "../../modules/storage"

  name_prefix           = local.name_prefix
  raw_bucket_name       = var.raw_bucket_name
  lakehouse_bucket_name = var.lakehouse_bucket_name
}

module "iam" {
  source = "../../modules/iam"

  name_prefix          = local.name_prefix
  raw_bucket_arn       = module.storage.raw_bucket_arn
  lakehouse_bucket_arn = module.storage.lakehouse_bucket_arn
  order_stream_arn     = module.streaming.order_events_stream_arn
}

module "glue" {
  source = "../../modules/glue"

  name_prefix       = local.name_prefix
  database_name     = var.glue_database_name
  paimon_warehouse  = module.storage.paimon_warehouse_uri
  pipeline_role_arn = module.iam.pipeline_role_arn
}

module "emr" {
  source = "../../modules/emr"

  name_prefix = local.name_prefix
  vpc_id      = module.network.vpc_id
  subnet_ids  = module.network.private_subnet_ids

  release_label        = var.emr_release_label
  maximum_cpu          = var.emr_maximum_cpu
  maximum_memory       = var.emr_maximum_memory
  maximum_disk         = var.emr_maximum_disk
  idle_timeout_minutes = var.emr_idle_timeout_minutes
}

module "streaming" {
  source = "../../modules/streaming"

  name_prefix     = local.name_prefix
  shard_count     = var.kinesis_shard_count
  retention_hours = var.kinesis_retention_hours
}

module "observability" {
  source = "../../modules/observability"

  name_prefix        = local.name_prefix
  log_retention_days = var.log_retention_days
}
