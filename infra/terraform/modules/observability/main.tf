resource "aws_cloudwatch_log_group" "pipeline" {
  name              = "/aws/peakorder/${var.name_prefix}/pipeline"
  retention_in_days = var.log_retention_days
}

resource "aws_sns_topic" "alerts" {
  name = "${var.name_prefix}-alerts"
}
