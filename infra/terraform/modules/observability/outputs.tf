output "pipeline_log_group_name" {
  description = "Pipeline CloudWatch log group."
  value       = aws_cloudwatch_log_group.pipeline.name
}

output "alerts_topic_arn" {
  description = "SNS topic ARN for alerts."
  value       = aws_sns_topic.alerts.arn
}
