resource "aws_kinesis_stream" "orders" {
  name             = "${var.name_prefix}-order-events"
  shard_count      = var.shard_count
  retention_period = var.retention_hours

  stream_mode_details {
    stream_mode = "PROVISIONED"
  }

  encryption_type = "KMS"
  kms_key_id      = "alias/aws/kinesis"

  tags = {
    Name = "${var.name_prefix}-order-events"
  }
}
