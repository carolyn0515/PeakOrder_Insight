output "pipeline_role_arn" {
  description = "Pipeline IAM role ARN."
  value       = aws_iam_role.pipeline.arn
}
