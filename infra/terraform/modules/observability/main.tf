resource "aws_cloudwatch_log_group" "pipeline" {
  name              = "/aws/peakorder/${var.name_prefix}/pipeline"
  retention_in_days = var.log_retention_days
}

resource "aws_sns_topic" "alerts" {
  name = "${var.name_prefix}-alerts"
}

resource "aws_cloudwatch_metric_alarm" "kinesis_peak_ingestion" {
  alarm_name          = "${var.name_prefix}-kinesis-peak-ingestion"
  alarm_description   = "Kinesis IncomingRecords crossed the peak-order replay threshold."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "IncomingRecords"
  namespace           = "AWS/Kinesis"
  period              = 60
  statistic           = "Sum"
  threshold           = 40000
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    StreamName = var.order_stream_name
  }
}
